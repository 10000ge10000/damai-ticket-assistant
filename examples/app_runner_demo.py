"""Simulated run of DamaiAppTicketRunner to demonstrate RunnerPhase transitions."""

from __future__ import annotations

from typing import Any, Dict, List
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from damai_appium import (
    AppTicketConfig,
    DamaiAppTicketRunner,
    LogLevel,
    RunnerPhase,
)


def main() -> None:
    logs: List[str] = []

    def logger(level: str, message: str, context: Dict[str, Any] | None = None) -> None:
        context_str = ""
        if context:
            context_parts = [f"{key}={value}" for key, value in context.items()]
            if context_parts:
                context_str = " (" + ", ".join(context_parts) + ")"
        logs.append(f"[{level.upper()}] {message}{context_str}")

    config = AppTicketConfig(
        server_url="http://127.0.0.1:4723",
        city="上海",
        price_index=0,
        users=["测试用户"],
        if_commit_order=False,
    )

    runner = DamaiAppTicketRunner(config=config, logger=logger)

    # Provide harmless stubs so the run does not require a real Appium server.
    runner._create_driver = lambda: _DummyDriver()  # type: ignore[assignment]
    runner._apply_driver_settings = lambda: None  # type: ignore[assignment]
    runner._select_city = lambda _city: True  # type: ignore[assignment]
    runner._tap_purchase_button = lambda: True  # type: ignore[assignment]
    runner._select_price = lambda: None  # type: ignore[assignment]
    runner._select_quantity = lambda: None  # type: ignore[assignment]
    runner._confirm_purchase = lambda: True  # type: ignore[assignment]
    runner._select_users = lambda _users: None  # type: ignore[assignment]
    runner._submit_order = lambda: None  # type: ignore[assignment]

    success = runner.run(max_retries=1)
    report = runner.get_last_report()

    print("演练结果: 成功" if success else "演练结果: 失败")
    print("当前阶段:", runner.current_phase.value)
    print("阶段轨迹:", " -> ".join(phase.value for phase in runner.phase_history))
    if report is not None:
        metrics = report.metrics
        duration = max(metrics.end_time - metrics.start_time, 0.0)
        print(
            "运行统计:",
            f"尝试 {metrics.attempts} 次 | 重试 {max(metrics.attempts - 1, 0)} 次 | 耗时 {duration:.2f}s",
        )
        if metrics.failure_reason:
            print("失败原因:", metrics.failure_reason)
    print("\n详细日志:")
    for entry in logs:
        print(entry)


class _DummyDriver:
    def update_settings(self, *_args, **_kwargs) -> None:
        return None

    def quit(self) -> None:
        return None


if __name__ == "__main__":
    main()
