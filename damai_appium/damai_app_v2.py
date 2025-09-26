"""Command line entry point for the modular Damai Appium runner."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from damai_appium import (
    AppTicketConfig,
    ConfigValidationError,
    DamaiAppTicketRunner,
    FailureReason,
    LogLevel,
)


def _console_logger(level: str, message: str, context: Optional[Dict[str, object]] = None) -> None:
    if context is None:
        context = {}
    ctx_repr = " ".join(f"{k}={v}" for k, v in context.items())
    if ctx_repr:
        print(f"[{level.upper()}] {message} | {ctx_repr}")
    else:
        print(f"[{level.upper()}] {message}")


def _make_session_logger(session_label: str):
    def _logger(level: str, message: str, context: Optional[Dict[str, object]] = None) -> None:
        merged: Dict[str, Any] = {"session": session_label}
        if context:
            merged.update(context)
        _console_logger(level, message, merged)

    return _logger


def _derive_session_label(config: AppTicketConfig, index: int) -> str:
    device_caps = config.device_caps or {}
    parts: List[str] = []
    device_name = device_caps.get("deviceName")
    udid = device_caps.get("udid")
    if device_name:
        parts.append(str(device_name))
    if udid and udid not in parts:
        parts.append(str(udid))
    if not parts:
        parts.append(config.server_url)
    descriptor = "/".join(parts)
    return f"device-{index}:{descriptor}"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Damai app ticket grabbing (Appium)")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="配置文件路径，默认使用 damai_appium/config.jsonc",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="失败重试次数（包含首次执行）",
    )
    parser.add_argument(
        "--export-report",
        type=Path,
        default=None,
        help="可选：将运行日志与统计导出为 JSON 文件",
    )
    return parser.parse_args()


def _print_summary(result: bool, report, *, session_label: Optional[str] = None) -> None:
    if report is None:
        prefix = "[SUMMARY]" if session_label is None else f"[SUMMARY][{session_label}]"
        print(f"{prefix} No run report available.")
        return

    metrics = report.metrics
    duration = max(metrics.end_time - metrics.start_time, 0.0)
    retries = max(metrics.attempts - 1, 0)
    status = "SUCCESS" if result else "FAILED"
    prefix = "[SUMMARY]" if session_label is None else f"[SUMMARY][{session_label}]"
    print(
        f"{prefix} Status={status} Attempts={metrics.attempts} Retries={retries} "
        f"Duration={duration:.2f}s FinalPhase={metrics.final_phase.value}"
    )
    if not result:
        reason = metrics.failure_reason or "未能成功完成流程"
        extra = (
            f" (code={metrics.failure_code.value})" if metrics.failure_code else ""
        )
        print(f"{prefix} FailureReason={reason}{extra}")
        if metrics.failure_code == FailureReason.MAX_RETRIES:
            print(f"{prefix} 提示: 已达到最大重试次数，可尝试调整参数或检查网络。")


def _export_reports(target: Path, runs: List[Dict[str, Any]]) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    export_payload = {
        "generated_at": now_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "overall_success": all(item["success"] for item in runs),
        "runs": [
            {
                "session": item["session"],
                "success": item["success"],
                "config": {
                    "server_url": item["config"].server_url,
                    "users": item["config"].users,
                    "keyword": item["config"].keyword,
                    "city": item["config"].city,
                    "date": item["config"].date,
                    "price": item["config"].price,
                    "price_index": item["config"].price_index,
                    "device_caps": item["config"].device_caps,
                },
                "report": item["report"].to_dict() if item["report"] else None,
            }
            for item in runs
        ],
    }
    target.write_text(json.dumps(export_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main() -> int:
    args = _parse_args()
    try:
        configs = AppTicketConfig.load_all(args.config)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return 2
    except ConfigValidationError as exc:
        print(f"[ERROR] {exc.message}")
        for item in exc.errors:
            print(f"        - {item}")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] 配置加载失败: {exc}")
        return 2
    runs: List[Dict[str, Any]] = []
    total = len(configs)
    print(f"[INFO] 发现 {total} 个待执行会话。")

    overall_success = True
    for index, config in enumerate(configs, start=1):
        session_label = _derive_session_label(config, index)
        logger = _make_session_logger(session_label)
        print(f"[INFO] 开始执行 {session_label}")
        runner = DamaiAppTicketRunner(config=config, logger=logger)
        success = runner.run(max(args.retries, 1))
        report = runner.get_last_report()
        _print_summary(success, report, session_label=session_label)
        if not success:
            overall_success = False
        runs.append({"session": session_label, "success": success, "config": config, "report": report})

    print(
        f"[SUMMARY] 所有会话执行完成，共 {total} 个，其中 {sum(1 for item in runs if item['success'])} 个成功。"
    )

    if args.export_report:
        if not runs:
            print("[SUMMARY] No report to export.")
        else:
            export_target = _export_reports(Path(args.export_report), runs)
            print(f"[SUMMARY] 汇总报告已导出: {export_target}")

    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
