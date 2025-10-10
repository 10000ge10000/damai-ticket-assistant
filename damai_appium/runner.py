"""Appium-based ticket grabbing runner for the Damai mobile app."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from appium import webdriver
from appium.options.common.base import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from .config import AppTicketConfig


Logger = Callable[[str, str, Dict[str, Any]], None]
StopSignal = Callable[[], bool]
DriverFactory = Callable[[str, Dict[str, Any]], Any]


class LogLevel(str, Enum):
    STEP = "step"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class RunnerPhase(str, Enum):
    INIT = "init"
    CONNECTING = "connecting"
    APPLYING_SETTINGS = "applying_settings"
    SELECTING_CITY = "selecting_city"
    TAPPING_PURCHASE = "tapping_purchase"
    SELECTING_PRICE = "selecting_price"
    SELECTING_QUANTITY = "selecting_quantity"
    CONFIRMING_PURCHASE = "confirming_purchase"
    SELECTING_USERS = "selecting_users"
    SUBMITTING_ORDER = "submitting_order"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


class TicketRunnerError(RuntimeError):
    """Base exception for ticket runner failures."""


class TicketRunnerStopped(TicketRunnerError):
    """Raised when the runner is stopped externally."""


class FailureReason(str, Enum):
    USER_STOP = "user_stop"
    APPIUM_CONNECTION = "appium_connection_failed"
    FLOW_FAILURE = "flow_failure"
    UNEXPECTED = "unexpected_error"
    MAX_RETRIES = "max_retries_reached"


@dataclass
class TicketRunLogEntry:
    timestamp: float
    level: LogLevel
    message: str
    phase: RunnerPhase
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        iso_time = datetime.fromtimestamp(self.timestamp).isoformat(timespec="milliseconds")
        return {
            "timestamp": self.timestamp,
            "timestamp_iso": iso_time,
            "level": self.level.value,
            "message": self.message,
            "phase": self.phase.value,
            "context": self.context,
        }


@dataclass
class TicketRunMetrics:
    start_time: float
    end_time: float
    attempts: int
    success: bool
    final_phase: RunnerPhase
    failure_reason: Optional[str]
    failure_code: Optional[FailureReason]

    def to_dict(self) -> Dict[str, Any]:
        duration = max(self.end_time - self.start_time, 0.0)
        return {
            "start_time": self.start_time,
            "start_time_iso": datetime.fromtimestamp(self.start_time).isoformat(timespec="milliseconds"),
            "end_time": self.end_time,
            "end_time_iso": datetime.fromtimestamp(self.end_time).isoformat(timespec="milliseconds"),
            "duration_seconds": round(duration, 3),
            "attempts": self.attempts,
            "retries": max(self.attempts - 1, 0),
            "success": self.success,
            "final_phase": self.final_phase.value,
            "failure_reason": self.failure_reason,
            "failure_code": self.failure_code.value if self.failure_code else None,
        }


@dataclass
class TicketRunReport:
    metrics: TicketRunMetrics
    logs: List[TicketRunLogEntry]
    phase_history: List[RunnerPhase]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metrics": self.metrics.to_dict(),
            "phase_history": [phase.value for phase in self.phase_history],
            "logs": [entry.to_dict() for entry in self.logs],
        }

    def dump_json(self, path: Union[str, Path], *, indent: int = 2) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as fp:
            json.dump(self.to_dict(), fp, ensure_ascii=False, indent=indent)
        return target


def _default_logger(level: str, message: str, context: Optional[Dict[str, Any]] = None) -> None:
    context = context or {}
    extra = " ".join(f"{key}={value}" for key, value in context.items())
    if extra:
        print(f"[{level.upper()}] {message} | {extra}")
    else:
        print(f"[{level.upper()}] {message}")


@dataclass
class DamaiAppTicketRunner:
    """Encapsulates the Damai Appium ticket grabbing workflow."""

    config: AppTicketConfig
    logger: Logger = _default_logger
    stop_signal: StopSignal = lambda: False
    driver_factory: Optional[DriverFactory] = None
    current_phase: RunnerPhase = field(init=False)
    phase_history: List[RunnerPhase] = field(init=False)
    last_report: Optional[TicketRunReport] = field(init=False, default=None)

    _log_entries: List[TicketRunLogEntry] = field(init=False, default_factory=list)
    _run_start_time: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        if self.logger is None:
            self.logger = _default_logger
        if self.stop_signal is None:
            self.stop_signal = lambda: False
        self._driver = None
        self._wait: Optional[WebDriverWait] = None
        self.current_phase = RunnerPhase.INIT
        self.phase_history = [RunnerPhase.INIT]
        self._log_entries = []
        self._run_start_time = 0.0
        self.last_report = None

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def _transition_to(self, phase: RunnerPhase) -> None:
        if phase == self.current_phase:
            return
        self.current_phase = phase
        self.phase_history.append(phase)

    def _mark_failure(self) -> None:
        if self.current_phase != RunnerPhase.FAILED:
            self._transition_to(RunnerPhase.FAILED)

    def _mark_stopped(self) -> None:
        if self.current_phase != RunnerPhase.STOPPED:
            self._transition_to(RunnerPhase.STOPPED)

    def _ensure_driver(self):
        if self._driver is None:
            raise TicketRunnerError("Appium driver 尚未初始化")
        return self._driver

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self, max_retries: int = 1) -> bool:
        """Run the ticket grabbing flow with optional retries."""
        self.current_phase = RunnerPhase.INIT
        self.phase_history = [RunnerPhase.INIT]
        self._log_entries = []
        self.last_report = None
        self._run_start_time = time.time()

        attempts = 0
        success = False
        failure_code: Optional[FailureReason] = None
        failure_message: Optional[str] = None

        max_retries = max(1, max_retries)

        while attempts < max_retries and not self._should_stop():
            attempts += 1
            self._log(
                LogLevel.INFO,
                f"第 {attempts} 次尝试",
                {"attempt": attempts, "max_retries": max_retries},
            )
            try:
                if self._execute_once():
                    success = True
                    self._log(LogLevel.SUCCESS, "抢票流程执行完成", {"attempt": attempts})
                    break
            except TicketRunnerStopped as exc:
                self._mark_stopped()
                failure_code = FailureReason.USER_STOP
                failure_message = str(exc).strip() or "用户已停止流程"
                self._log(LogLevel.WARNING, failure_message, {"attempt": attempts})
                break
            except TicketRunnerError as exc:
                self._mark_failure()
                failure_code, failure_message = self._diagnose_failure(exc)
                self._log(LogLevel.ERROR, failure_message, {"attempt": attempts})
            except Exception as exc:  # noqa: BLE001
                self._mark_failure()
                failure_code = FailureReason.UNEXPECTED
                failure_message = f"未预期的异常: {exc}"
                self._log(LogLevel.ERROR, failure_message, {"attempt": attempts})

            if not success and attempts < max_retries and not self._should_stop():
                self._log(LogLevel.INFO, "准备重试", {"attempt": attempts + 1})
                time.sleep(max(self.config.retry_delay, 0))

        end_time = time.time()

        if not success:
            if failure_code is None:
                if self.current_phase == RunnerPhase.STOPPED or self._should_stop():
                    failure_code = FailureReason.USER_STOP
                    failure_message = failure_message or "流程被请求停止"
                else:
                    failure_code = FailureReason.MAX_RETRIES
                    failure_message = failure_message or "达到最大重试次数仍未成功"

        duration = max(end_time - self._run_start_time, 0.0)
        stats_context = {
            "attempts": attempts,
            "retries": max(attempts - 1, 0),
            "duration": round(duration, 3),
            "success": success,
        }
        if failure_code:
            stats_context["failure_code"] = failure_code.value
        self._log(LogLevel.INFO, "执行统计", stats_context)

        metrics = TicketRunMetrics(
            start_time=self._run_start_time,
            end_time=end_time,
            attempts=attempts,
            success=success,
            final_phase=self.current_phase,
            failure_reason=failure_message,
            failure_code=failure_code,
        )

        self.last_report = TicketRunReport(
            metrics=metrics,
            logs=list(self._log_entries),
            phase_history=list(self.phase_history),
        )

        return success

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _execute_once(self) -> bool:
        try:
            self._ensure_not_stopped()
            self._transition_to(RunnerPhase.CONNECTING)
            self._log(LogLevel.STEP, "连接 Appium server")
            try:
                self._driver = self._create_driver()
            except Exception as exc:  # noqa: BLE001
                raise TicketRunnerError(f"连接 Appium server 失败: {exc}") from exc

            driver = self._ensure_driver()
            self._wait = WebDriverWait(driver, self.config.wait_timeout)

            self._transition_to(RunnerPhase.APPLYING_SETTINGS)
            self._apply_driver_settings()

            self._log(LogLevel.STEP, "开始执行抢票流程")
            result = self._perform_ticket_flow()
            return result
        finally:
            self._cleanup_driver()

    def _create_driver(self):
        caps = self.config.desired_capabilities
        if self.driver_factory is not None:
            driver = self.driver_factory(self.config.endpoint, caps)
        else:
            options = AppiumOptions()
            options.load_capabilities(caps)
            driver = webdriver.Remote(self.config.endpoint, options=options)  # type: ignore[attr-defined]
        return driver

    def _apply_driver_settings(self) -> None:
        if not self._driver:
            return
        try:
            self._driver.update_settings(
                {
                    "waitForIdleTimeout": 0,
                    "actionAcknowledgmentTimeout": 0,
                    "keyInjectionDelay": 0,
                    "waitForSelectorTimeout": 300,
                    "ignoreUnimportantViews": False,
                    "allowInvisibleElements": True,
                    "enableNotificationListener": False,
                }
            )
        except Exception as exc:  # noqa: BLE001
            self._log(LogLevel.WARNING, f"更新驱动设置失败: {exc}")

    def _perform_ticket_flow(self) -> bool:
        try:
            self._ensure_not_stopped()
            if self.config.city:
                self._transition_to(RunnerPhase.SELECTING_CITY)
                self._log(LogLevel.STEP, f"选择城市: {self.config.city}")
                if not self._select_city(self.config.city):
                    self._log(LogLevel.WARNING, f"未找到城市 {self.config.city}")

            self._ensure_not_stopped()
            self._transition_to(RunnerPhase.TAPPING_PURCHASE)
            self._log(LogLevel.STEP, "尝试点击预约/购买按钮")
            if not self._tap_purchase_button():
                raise TicketRunnerError("未能找到预约/购买入口")

            self._ensure_not_stopped()
            if self.config.price_index is not None:
                self._transition_to(RunnerPhase.SELECTING_PRICE)
                self._log(LogLevel.STEP, "选择票价")
                self._select_price()

            self._ensure_not_stopped()
            if self.config.users and len(self.config.users) > 1:
                self._transition_to(RunnerPhase.SELECTING_QUANTITY)
                self._log(LogLevel.STEP, "选择数量")
                self._select_quantity()

            self._ensure_not_stopped()
            self._transition_to(RunnerPhase.CONFIRMING_PURCHASE)
            self._log(LogLevel.STEP, "确认购买")
            if not self._confirm_purchase():
                raise TicketRunnerError("未能进入确认页面")

            self._ensure_not_stopped()
            if self.config.users:
                self._transition_to(RunnerPhase.SELECTING_USERS)
                self._log(LogLevel.STEP, "选择观演人")
                self._select_users(self.config.users)

            self._ensure_not_stopped()
            self._transition_to(RunnerPhase.SUBMITTING_ORDER)
            self._log(LogLevel.STEP, "提交订单")
            self._submit_order()

            self._transition_to(RunnerPhase.COMPLETED)
            return True
        except TicketRunnerStopped:
            self._mark_stopped()
            raise
        except TicketRunnerError:
            self._mark_failure()
            raise
        except Exception as exc:  # noqa: BLE001
            self._mark_failure()
            phase = self.current_phase.value if isinstance(self.current_phase, RunnerPhase) else str(self.current_phase)
            raise TicketRunnerError(f"执行阶段 {phase} 出现异常: {exc}") from exc

    # ------------------------------------------------------------------
    # Appium interaction primitives
    # ------------------------------------------------------------------
    def _smart_wait_and_click(
        self,
        selector: Sequence[Any],
        backups: Sequence[Sequence[Any]] = (),
        timeout: float = 1.5,
    ) -> bool:
        driver = self._ensure_driver()
        selectors: List[Sequence[Any]] = [selector, *backups]
        for by, value in selectors:
            self._ensure_not_stopped()
            try:
                element = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((by, value))
                )
                rect = element.rect
                driver.execute_script(
                    "mobile: clickGesture",
                    {
                        "x": rect["x"] + rect["width"] // 2,
                        "y": rect["y"] + rect["height"] // 2,
                        "duration": 50,
                    },
                )
                return True
            except TimeoutException:
                continue
        return False

    def _ultra_fast_click(self, by: Any, value: Any, timeout: float = 1.5) -> bool:
        driver = self._ensure_driver()
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            rect = element.rect
            driver.execute_script(
                "mobile: clickGesture",
                {
                    "x": rect["x"] + rect["width"] // 2,
                    "y": rect["y"] + rect["height"] // 2,
                    "duration": 50,
                },
            )
            return True
        except TimeoutException:
            return False

    def _ultra_batch_click(
        self, selectors: Iterable[Sequence[Any]], timeout: float = 2.0
    ) -> None:
        driver = self._ensure_driver()
        coordinates: List[Dict[str, Any]] = []
        for by, value in selectors:
            self._ensure_not_stopped()
            try:
                element = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((by, value))
                )
                rect = element.rect
                coordinates.append(
                    {
                        "x": rect["x"] + rect["width"] // 2,
                        "y": rect["y"] + rect["height"] // 2,
                        "label": value,
                    }
                )
            except TimeoutException:
                self._log(LogLevel.WARNING, f"未找到元素: {value}")
            except Exception as exc:  # noqa: BLE001
                self._log(LogLevel.WARNING, f"查找元素失败 {value}: {exc}")

        for item in coordinates:
            self._ensure_not_stopped()
            driver.execute_script(
                "mobile: clickGesture",
                {
                    "x": item["x"],
                    "y": item["y"],
                    "duration": 30,
                },
            )
            time.sleep(0.01)

    # ------------------------------------------------------------------
    # Flow steps
    # ------------------------------------------------------------------
    def _select_city(self, city: str) -> bool:
        selectors = [
            (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{city}")'),
            (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().textContains("{city}")'),
            (By.XPATH, f'//*[@text="{city}"]'),
        ]
        return self._smart_wait_and_click(selectors[0], selectors[1:])

    def _tap_purchase_button(self) -> bool:
        selectors = [
            (By.ID, "cn.damai:id/trade_project_detail_purchase_status_bar_container_fl"),
            (
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().textMatches(".*预约.*|.*购买.*|.*立即.*")',
            ),
            (By.XPATH, '//*[contains(@text,"预约") or contains(@text,"购买")]'),
        ]
        return self._smart_wait_and_click(selectors[0], selectors[1:])

    def _select_price(self) -> None:
        """Robust ticket price selection with multiple fallbacks and auto-scroll.

        Strategy:
        - Wait for any known container id to appear
        - Prefer clickable child FrameLayout list, then generic clickable children
        - Use index from config.price_index, scroll container if target not in view
        - Optional text fallback when config.price present
        """
        if self.config.price_index is None and not getattr(self.config, "price", None):
            return

        driver = self._ensure_driver()
        wait = WebDriverWait(driver, max(self.config.wait_timeout, 1.0))
        container_ids = [
            "cn.damai:id/project_detail_perform_price_flowlayout",
            # 若 UI 变更，可尝试其它容器 id（兼容大小写或新命名）
            "cn.damai:id/project_detail_perform_price_flowLayout",
            "cn.damai:id/project_detail_perform_price_layout",
        ]

        container = None
        for cid in container_ids:
            try:
                container = wait.until(EC.presence_of_element_located((By.ID, cid)))
                break
            except TimeoutException:
                continue

        if container is None:
            self._log(LogLevel.WARNING, "未找到票价容器，跳过票价选择")
            return

        # 收集候选子项（优先 FrameLayout 且 clickable）
        try:
            items = container.find_elements(By.XPATH, './/android.widget.FrameLayout[@clickable="true"]')
            if not items:
                # 退化为查找任何可点击子元素
                items = container.find_elements(By.XPATH, './/*[@clickable="true"]')
        except Exception as exc:  # noqa: BLE001
            self._log(LogLevel.WARNING, f"收集票价子项失败: {exc}")
            items = []

        # 如果有 price_index，按索引选择目标
        target_elem = None
        if self.config.price_index is not None:
            idx = int(self.config.price_index)
            if items and 0 <= idx < len(items):
                target_elem = items[idx]
            else:
                self._log(
                    LogLevel.WARNING,
                    f"票价索引越界或无可点击子项: index={idx}, items={len(items)}"
                )

        # 若未命中索引，尝试文本匹配（当 config.price 提供时）
        if target_elem is None and getattr(self.config, "price", None):
            price_text = str(self.config.price).strip()
            if price_text:
                # 优先使用 UiAutomator 文本匹配
                try:
                    target_elem = container.find_element(
                        AppiumBy.ANDROID_UIAUTOMATOR,
                        f'new UiSelector().textContains("{price_text}")'
                    )
                except Exception:
                    # 退化为 XPath 文本包含
                    try:
                        target_elem = container.find_element(By.XPATH, f'.//*[contains(@text,"{price_text}")]')
                    except Exception:
                        target_elem = None

        if target_elem is None:
            self._log(LogLevel.WARNING, "未找到目标票价项，跳过票价选择")
            return

        # 若目标不在可视范围，尝试在容器内滚动将其带入视图
        try:
            # 最多滚动 5 次（方向向下）
            attempts = 0
            while attempts < 5 and not target_elem.is_displayed():
                crect = container.rect
                try:
                    driver.execute_script(
                        "mobile: scrollGesture",
                        {
                            "left": crect["x"],
                            "top": crect["y"],
                            "width": crect["width"],
                            "height": crect["height"],
                            "direction": "down",
                            "percent": 0.8,
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    self._log(LogLevel.WARNING, f"滚动失败: {exc}")
                    break
                attempts += 1
                time.sleep(0.05)
        except Exception as exc:  # noqa: BLE001
            self._log(LogLevel.WARNING, f"可视区域检查失败: {exc}")

        # 使用原生 clickGesture 点击目标（优先 elementId）
        try:
            if hasattr(target_elem, "id"):
                driver.execute_script("mobile: clickGesture", {"elementId": target_elem.id})
            else:
                rect = target_elem.rect
                driver.execute_script(
                    "mobile: clickGesture",
                    {
                        "x": rect["x"] + rect["width"] // 2,
                        "y": rect["y"] + rect["height"] // 2,
                        "duration": 50,
                    },
                )
            self._log(LogLevel.INFO, "票价选择完成", {"price_index": self.config.price_index})
        except Exception as exc:  # noqa: BLE001
            self._log(LogLevel.WARNING, f"票价选择点击异常: {exc}")

    def _select_quantity(self) -> None:
        """Set ticket quantity based on available viewer toggles when possible.

        Behavior:
        - 统计确认页可点击的观演人切换控件数量（CheckBox/RadioButton/Switch/ImageView）
        - 若找到控件，目标购票数 = 控件数量（至少为 1）
        - 使用“加号按钮”(img_jia) 快速点按设定数量
        """
        driver = self._ensure_driver()
        try:
            toggles: List[Any] = []
            try:
                toggles.extend(driver.find_elements(By.XPATH, '//*[@class="android.widget.CheckBox" and @clickable="true"]'))
                toggles.extend(driver.find_elements(By.XPATH, '//*[@class="android.widget.RadioButton" and @clickable="true"]'))
                toggles.extend(driver.find_elements(By.XPATH, '//*[@class="android.widget.Switch" and @clickable="true"]'))
                toggles.extend(driver.find_elements(By.XPATH, '//*[@class="android.widget.ImageView" and @clickable="true"]'))
            except Exception as exc:  # noqa: BLE001
                self._log(LogLevel.WARNING, f"统计观演人切换控件失败: {exc}")

            desired_qty = max(1, len(toggles))
            if desired_qty <= 1:
                return

            plus_button = driver.find_element(By.ID, "img_jia")
            rect = plus_button.rect
            for _ in range(desired_qty - 1):
                self._ensure_not_stopped()
                driver.execute_script(
                    "mobile: clickGesture",
                    {
                        "x": rect["x"] + rect["width"] // 2,
                        "y": rect["y"] + rect["height"] // 2,
                        "duration": 50,
                    },
                )
                time.sleep(0.02)
        except NoSuchElementException:
            # 无需调整数量
            return
        except Exception as exc:  # noqa: BLE001
            self._log(LogLevel.WARNING, f"人数选择异常: {exc}")

    def _confirm_purchase(self) -> bool:
        driver = self._ensure_driver()
        if self._ultra_fast_click(By.ID, "btn_buy_view"):
            return True
        return self._ultra_fast_click(
            AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches(".*确定.*|.*购买.*")'
        )

    def _select_users(self, users: Sequence[str]) -> None:
        """Robust viewer selection on the confirm page.

        Strategy:
        - 默认尝试勾选未选中的开关/圆点图标（CheckBox/RadioButton/Switch/ImageView）
        - 若未检测到图标，再逐个按姓名文本匹配（精确→包含），点击最近的可点击祖先行
        - 不在可视范围时滚动并重试，最大尝试 6 次
        - 全程使用 mobile: clickGesture 原生点击
        """
        driver = self._ensure_driver()
        wait = WebDriverWait(driver, max(self.config.wait_timeout, 1.0))

        # 获取当前窗口矩形，用于 scrollGesture
        try:
            window = driver.get_window_rect()
        except Exception:  # noqa: BLE001
            window = {"x": 0, "y": 0, "width": 1080, "height": 1920}

        def _click_center(elem: Any) -> bool:
            try:
                rect = elem.rect
                driver.execute_script(
                    "mobile: clickGesture",
                    {
                        "x": rect["x"] + rect["width"] // 2,
                        "y": rect["y"] + rect["height"] // 2,
                        "duration": 50,
                    },
                )
                return True
            except Exception as exc:  # noqa: BLE001
                self._log(LogLevel.WARNING, f"点击观演人控件失败: {exc}")
                return False

        def _scroll_down() -> None:
            try:
                driver.execute_script(
                    "mobile: scrollGesture",
                    {
                        "left": window["x"],
                        "top": window["y"],
                        "width": window["width"],
                        "height": window["height"],
                        "direction": "down",
                        "percent": 0.85,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._log(LogLevel.WARNING, f"观演人滚动失败: {exc}")

        # 1) 默认全选：尝试勾选未选中的切换控件（CheckBox/RadioButton/Switch/ImageView）
        attempts = 0
        toggles_clicked = 0
        while attempts < 6:
            toggles: List[Any] = []
            try:
                toggles.extend(driver.find_elements(By.XPATH, '//*[@class="android.widget.CheckBox" and @clickable="true"]'))
                toggles.extend(driver.find_elements(By.XPATH, '//*[@class="android.widget.RadioButton" and @clickable="true"]'))
                toggles.extend(driver.find_elements(By.XPATH, '//*[@class="android.widget.Switch" and @clickable="true"]'))
                toggles.extend(driver.find_elements(By.XPATH, '//*[@class="android.widget.ImageView" and @clickable="true"]'))
            except Exception as exc:  # noqa: BLE001
                self._log(LogLevel.WARNING, f"查找观演人切换控件失败: {exc}")
                toggles = []

            unchecked: List[Any] = []
            for t in toggles:
                try:
                    checked = (t.get_attribute("checked") or "").lower()
                    if checked not in ("true", "1", "yes"):
                        if t.is_displayed():
                            unchecked.append(t)
                except Exception:
                    if t.is_displayed():
                        unchecked.append(t)

            if unchecked:
                for t in unchecked:
                    if _click_center(t):
                        toggles_clicked += 1
                        time.sleep(0.02)
                break
            else:
                _scroll_down()
                attempts += 1
                time.sleep(0.05)

        if toggles_clicked > 0:
            self._log(LogLevel.INFO, "已通过图标控件勾选观演人", {"count": toggles_clicked})
            return

        for user in users:
            found = False
            attempts = 0
            while attempts < 6 and not found:
                self._ensure_not_stopped()
                elem = None
                try:
                    # 1) 精确文本匹配
                    try:
                        elem = wait.until(
                            EC.presence_of_element_located(
                                (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{user}")')
                            )
                        )
                    except TimeoutException:
                        # 2) 包含文本匹配
                        try:
                            elem = wait.until(
                                EC.presence_of_element_located(
                                    (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().textContains("{user}")')
                                )
                            )
                        except TimeoutException:
                            elem = None

                    if elem is not None:
                        # 优先选择最近的可点击祖先节点，保证命中行区域
                        clickable = None
                        try:
                            clickable = driver.find_element(
                                By.XPATH, f'//*[@text="{user}"]/ancestor::*[@clickable="true"][1]'
                            )
                        except Exception:  # noqa: BLE001
                            try:
                                clickable = driver.find_element(
                                    By.XPATH, f'//*[contains(@text,"{user}")]/ancestor::*[@clickable="true"][1]'
                                )
                            except Exception:  # noqa: BLE001
                                clickable = None

                        target = clickable or elem
                        try:
                            rect = target.rect
                            driver.execute_script(
                                "mobile: clickGesture",
                                {
                                    "x": rect["x"] + rect["width"] // 2,
                                    "y": rect["y"] + rect["height"] // 2,
                                    "duration": 50,
                                },
                            )
                            found = True
                            time.sleep(0.02)
                            continue
                        except Exception as exc:  # noqa: BLE001
                            self._log(LogLevel.WARNING, f"点击观演人失败: {user} | {exc}")

                    # 3) 未找到或未能点击：向下滚动并重试
                    try:
                        driver.execute_script(
                            "mobile: scrollGesture",
                            {
                                "left": window["x"],
                                "top": window["y"],
                                "width": window["width"],
                                "height": window["height"],
                                "direction": "down",
                                "percent": 0.85,
                            },
                        )
                    except Exception as exc:  # noqa: BLE001
                        self._log(LogLevel.WARNING, f"观演人滚动失败: {exc}")
                    attempts += 1
                    time.sleep(0.05)
                except Exception as exc:  # noqa: BLE001
                    attempts += 1
                    self._log(LogLevel.WARNING, f"选择观演人异常: {user} | {exc}")
                    time.sleep(0.05)

            if not found:
                self._log(LogLevel.WARNING, f"未能选择观演人: {user}")

    def _submit_order(self) -> None:
        self._ensure_driver()
        if self.config.if_commit_order:
            self._smart_wait_and_click(
                (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("立即提交")'),
                [
                    (
                        AppiumBy.ANDROID_UIAUTOMATOR,
                        'new UiSelector().textMatches(".*提交.*|.*确认.*")',
                    ),
                    (By.XPATH, '//*[contains(@text,"提交")]'),
                ],
            )

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _cleanup_driver(self) -> None:
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:  # noqa: BLE001
                pass
            finally:
                self._driver = None
                self._wait = None

    def _ensure_not_stopped(self) -> None:
        if self._should_stop():
            raise TicketRunnerStopped("流程被请求停止")

    def _should_stop(self) -> bool:
        try:
            return bool(self.stop_signal())
        except Exception:  # noqa: BLE001
            return False

    def _diagnose_failure(self, exc: Exception) -> Tuple[FailureReason, str]:
        message = str(exc).strip() or exc.__class__.__name__
        if isinstance(exc, TicketRunnerStopped):
            return FailureReason.USER_STOP, message or "用户已停止流程"
        if isinstance(exc, TicketRunnerError):
            if "连接 Appium server" in message:
                return FailureReason.APPIUM_CONNECTION, message
            return FailureReason.FLOW_FAILURE, message
        return FailureReason.UNEXPECTED, f"未预期的异常: {message}"

    def _log(self, level: LogLevel, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        if context is None:
            context = {}
        phase = self.current_phase
        context_copy = dict(context)
        context_copy.setdefault("phase", phase.value if isinstance(phase, RunnerPhase) else str(phase))
        entry = TicketRunLogEntry(
            timestamp=time.time(),
            level=level,
            message=message,
            phase=phase,
            context=context_copy,
        )
        self._log_entries.append(entry)
        try:
            self.logger(level.value, message, context_copy)
        except TypeError:
            try:
                self.logger(level.value, message)  # type: ignore[misc]
            except Exception:  # noqa: BLE001
                pass
        except Exception:  # noqa: BLE001
            pass

    def get_last_report(self) -> Optional[TicketRunReport]:
        return self.last_report

    def export_last_report(self, path: Union[str, Path], *, indent: int = 2) -> Optional[Path]:
        if self.last_report is None:
            return None
        return self.last_report.dump_json(path, indent=indent)