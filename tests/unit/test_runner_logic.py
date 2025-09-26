import json
from typing import Any, cast

import pytest

from damai_appium.config import AppTicketConfig
from damai_appium.runner import (
    DamaiAppTicketRunner,
    FailureReason,
    LogLevel,
    RunnerPhase,
    TicketRunnerError,
    TicketRunnerStopped,
)


class DummyDriver:
    def update_settings(self, *_args, **_kwargs):
        return None

    def quit(self):
        return None


@pytest.fixture()
def sample_config() -> AppTicketConfig:
    return AppTicketConfig(server_url="http://127.0.0.1:4723")


def test_should_stop_respects_signal(sample_config):
    runner = DamaiAppTicketRunner(sample_config, stop_signal=lambda: True)
    assert runner._should_stop() is True


def test_should_stop_handles_exceptions(sample_config):
    def broken_signal():
        raise RuntimeError("boom")

    runner = DamaiAppTicketRunner(sample_config, stop_signal=broken_signal)
    assert runner._should_stop() is False


def test_ensure_not_stopped_raises(sample_config):
    runner = DamaiAppTicketRunner(sample_config, stop_signal=lambda: True)
    with pytest.raises(TicketRunnerStopped):
        runner._ensure_not_stopped()


def test_log_falls_back_to_two_arg_logger(sample_config):
    calls = []

    def two_arg_logger(level, message):
        calls.append((level, message))

    runner = DamaiAppTicketRunner(sample_config, logger=cast(Any, two_arg_logger))
    runner._log(LogLevel.INFO, "hello", {"foo": "bar"})

    assert calls == [(LogLevel.INFO.value, "hello")]


def test_log_swallows_logger_errors(sample_config):
    def bad_logger(*_args, **_kwargs):
        raise RuntimeError("logger failed")

    runner = DamaiAppTicketRunner(sample_config, logger=cast(Any, bad_logger))
    runner._log(LogLevel.ERROR, "should not raise")


def test_run_stops_after_success(monkeypatch, sample_config):
    calls = []

    def fake_logger(level, message, context):
        calls.append((level, message, context))

    runner = DamaiAppTicketRunner(sample_config, logger=fake_logger, stop_signal=lambda: False)

    monkeypatch.setattr(DamaiAppTicketRunner, "_execute_once", lambda self: True)
    monkeypatch.setattr(DamaiAppTicketRunner, "_cleanup_driver", lambda self: None)

    result = runner.run(max_retries=3)

    assert result is True
    assert any(level == LogLevel.SUCCESS.value for level, _msg, _ctx in calls)
    assert any(level == LogLevel.INFO.value for level, _msg, ctx in calls if ctx.get("attempt") == 1)


def test_runner_phase_tracking(monkeypatch, sample_config):
    runner = DamaiAppTicketRunner(sample_config, stop_signal=lambda: False)
    runner.config.users = []
    runner.config.price_index = None

    runner._create_driver = lambda: DummyDriver()
    runner._apply_driver_settings = lambda: None
    runner._tap_purchase_button = lambda: True
    runner._confirm_purchase = lambda: True
    runner._select_price = lambda: None
    runner._select_quantity = lambda: None
    runner._select_users = lambda users: None
    runner._submit_order = lambda: None

    assert runner.run(max_retries=1) is True
    assert runner.current_phase == RunnerPhase.COMPLETED
    assert RunnerPhase.TAPPING_PURCHASE in runner.phase_history


def test_runner_failure_marks_phase(monkeypatch, sample_config):
    runner = DamaiAppTicketRunner(sample_config, stop_signal=lambda: False)
    runner.config.users = []
    runner.config.price_index = None

    runner._create_driver = lambda: DummyDriver()
    runner._apply_driver_settings = lambda: None
    runner._tap_purchase_button = lambda: False

    assert runner.run(max_retries=1) is False
    assert runner.current_phase == RunnerPhase.FAILED
    assert RunnerPhase.TAPPING_PURCHASE in runner.phase_history


def test_run_report_provides_metrics(monkeypatch, sample_config):
    runner = DamaiAppTicketRunner(sample_config, stop_signal=lambda: False)

    monkeypatch.setattr(DamaiAppTicketRunner, "_execute_once", lambda self: True)
    monkeypatch.setattr(DamaiAppTicketRunner, "_cleanup_driver", lambda self: None)

    assert runner.run(max_retries=2) is True

    report = runner.get_last_report()
    assert report is not None
    assert report.metrics.success is True
    assert report.metrics.attempts == 1
    assert report.metrics.failure_code is None
    assert report.logs, "Expected log entries to be recorded"


def test_run_report_failure_reason(monkeypatch, sample_config):
    runner = DamaiAppTicketRunner(sample_config, stop_signal=lambda: False)

    def failing_execute(self):
        raise TicketRunnerError("流程失败示例")

    monkeypatch.setattr(DamaiAppTicketRunner, "_execute_once", failing_execute)
    monkeypatch.setattr(DamaiAppTicketRunner, "_cleanup_driver", lambda self: None)

    assert runner.run(max_retries=1) is False

    report = runner.get_last_report()
    assert report is not None
    assert report.metrics.success is False
    assert report.metrics.failure_code == FailureReason.FLOW_FAILURE
    assert "流程失败示例" in (report.metrics.failure_reason or "")


def test_export_last_report(tmp_path, monkeypatch, sample_config):
    runner = DamaiAppTicketRunner(sample_config, stop_signal=lambda: False)
    monkeypatch.setattr(DamaiAppTicketRunner, "_execute_once", lambda self: True)
    monkeypatch.setattr(DamaiAppTicketRunner, "_cleanup_driver", lambda self: None)

    assert runner.run(max_retries=1)
    path = tmp_path / "report.json"
    exported = runner.export_last_report(path)
    assert exported is not None and exported.exists()

    payload = json.loads(exported.read_text(encoding="utf-8"))
    assert payload["metrics"]["success"] is True