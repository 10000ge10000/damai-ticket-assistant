import json
import sys

import pytest

from damai_appium import AppTicketConfig, RunnerPhase, damai_app_v2


@pytest.mark.parametrize("payload", [{}, {"retry_delay": -1}])
def test_cli_main_reports_validation_errors(tmp_path, monkeypatch, capsys, payload):
    config_path = tmp_path / "invalid_config.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["damai_app_v2", "--config", str(config_path)])

    exit_code = damai_app_v2.main()
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "[ERROR]" in captured.out
    assert str(config_path.name) in captured.out
    assert "server_url" in captured.out


def test_cli_main_reports_missing_file(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "missing.json"

    monkeypatch.setattr(sys, "argv", ["damai_app_v2", "--config", str(config_path)])

    exit_code = damai_app_v2.main()
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "[ERROR]" in captured.out
    assert config_path.as_posix() in captured.out


def test_cli_main_runs_all_device_configs(tmp_path, monkeypatch, capsys):
    report_path = tmp_path / "report.json"
    configs = [
        AppTicketConfig(
            server_url="http://localhost:4723/wd/hub",
            keyword="base",
            device_caps={"deviceName": "BaseDevice", "udid": "base-udid"},
        ),
        AppTicketConfig(
            server_url="http://localhost:4723/wd/hub",
            keyword="fail",
            device_caps={"deviceName": "OverrideDevice", "udid": "override-udid"},
        ),
    ]

    def _fake_load_all(cls, path=None):  # noqa: ARG001 - signature for classmethod compatibility
        return configs

    class DummyMetrics:
        def __init__(self, success: bool) -> None:
            self.start_time = 0.0
            self.end_time = 1.0
            self.attempts = 1
            self.final_phase = RunnerPhase.COMPLETED if success else RunnerPhase.FAILED
            self.failure_reason = None if success else "boom"
            self.failure_code = None

    class DummyReport:
        def __init__(self, success: bool) -> None:
            self.success = success
            self.metrics = DummyMetrics(success)

        def to_dict(self):  # noqa: D401 - simple proxy
            return {"metrics": {"success": self.success}}

    class DummyRunner:
        instances = []

        def __init__(self, config, logger=None, **_kwargs) -> None:
            self.config = config
            self.logger = logger
            self._report = DummyReport(success=config.keyword != "fail")
            DummyRunner.instances.append(self)

        def run(self, max_retries):
            self.max_retries = max_retries
            return self._report.success

        def get_last_report(self):
            return self._report

    monkeypatch.setattr(damai_app_v2, "DamaiAppTicketRunner", DummyRunner)
    monkeypatch.setattr(damai_app_v2.AppTicketConfig, "load_all", classmethod(_fake_load_all))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "damai_app_v2",
            "--retries",
            "2",
            "--export-report",
            str(report_path),
        ],
    )

    exit_code = damai_app_v2.main()
    captured = capsys.readouterr()

    assert exit_code == 1, captured.out
    assert len(DummyRunner.instances) == 2
    assert DummyRunner.instances[0].config.keyword == "base"
    assert DummyRunner.instances[1].config.keyword == "fail"
    assert DummyRunner.instances[0].max_retries == 2
    assert "device-1" in captured.out
    assert "device-2" in captured.out

    export_data = json.loads(report_path.read_text(encoding="utf-8"))
    assert export_data["overall_success"] is False
    assert len(export_data["runs"]) == 2
    sessions = [item["session"] for item in export_data["runs"]]
    assert sessions[0].startswith("device-1")
    assert sessions[1].startswith("device-2")
