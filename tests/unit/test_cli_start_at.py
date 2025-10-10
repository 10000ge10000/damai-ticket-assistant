import sys
from datetime import datetime, timezone, timedelta

import pytest

from damai_appium import AppTicketConfig, damai_app_v2
from damai_appium.runner import RunnerPhase


class DummyRunner:
    instances = []

    def __init__(self, config, logger=None, **_kwargs) -> None:
        self.config = config
        self.logger = logger
        DummyRunner.instances.append(self)

    def run(self, max_retries):
        self.max_retries = max_retries
        # Always succeed for these tests
        return True

    def get_last_report(self):
        class _Metrics:
            def __init__(self):
                self.start_time = 0.0
                self.end_time = 1.0
                self.attempts = 1
                self.final_phase = RunnerPhase.COMPLETED
                self.failure_reason = None
                self.failure_code = None

        class _Report:
            def __init__(self):
                self.metrics = _Metrics()

            def to_dict(self):
                return {"metrics": {"success": True}}

        return _Report()


@pytest.fixture()
def sample_configs() -> list[AppTicketConfig]:
    return [
        AppTicketConfig(
            server_url="http://127.0.0.1:4723/wd/hub",
            device_caps={"deviceName": "DevA", "udid": "udid-a"},
        ),
        AppTicketConfig(
            server_url="http://127.0.0.1:4723/wd/hub",
            device_caps={"deviceName": "DevB", "udid": "udid-b"},
        ),
    ]


def test_cli_start_at_invokes_wait(monkeypatch, sample_configs):
    # Force CLI to load our sample configs
    def _fake_load_all(cls, path=None):  # noqa: ARG001 - signature compatibility
        return sample_configs

    DummyRunner.instances.clear()
    monkeypatch.setattr(damai_app_v2.AppTicketConfig, "load_all", classmethod(_fake_load_all))
    monkeypatch.setattr(damai_app_v2, "DamaiAppTicketRunner", DummyRunner)

    # Simulate a near-future start time
    target_dt = datetime.now(timezone.utc) + timedelta(seconds=2)
    monkeypatch.setattr(damai_app_v2, "_parse_start_at_text", lambda _text: target_dt)

    captured = []

    def _fake_wait_until_utc(target_utc, warmup_sec=0, server_url=None):
        captured.append((target_utc, warmup_sec, server_url))
        # Do not actually sleep

    monkeypatch.setattr(damai_app_v2, "_wait_until_utc", _fake_wait_until_utc)

    # Provide CLI args including start-at & warmup-sec
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "damai_app_v2",
            "--retries",
            "2",
            "--start-at",
            "2025-10-01 20:00:00",
            "--warmup-sec",
            "120",
        ],
    )

    exit_code = damai_app_v2.main()

    assert exit_code == 0
    assert len(DummyRunner.instances) == len(sample_configs)
    assert len(captured) == 1
    tgt, warm, server = captured[0]
    # The wait function should receive our parsed target UTC and warmup seconds
    assert isinstance(tgt, datetime)
    assert warm == 120
    assert server == sample_configs[0].server_url


def test_cli_start_at_past_time_executes_immediately(monkeypatch, sample_configs):
    # Force CLI to load our sample configs
    def _fake_load_all(cls, path=None):  # noqa: ARG001
        return sample_configs

    DummyRunner.instances.clear()
    monkeypatch.setattr(damai_app_v2.AppTicketConfig, "load_all", classmethod(_fake_load_all))
    monkeypatch.setattr(damai_app_v2, "DamaiAppTicketRunner", DummyRunner)

    # Simulate a past start time
    target_dt = datetime.now(timezone.utc) - timedelta(seconds=5)
    monkeypatch.setattr(damai_app_v2, "_parse_start_at_text", lambda _text: target_dt)

    captured = []

    def _fake_wait_until_utc(target_utc, warmup_sec=0, server_url=None):
        # For past time, the function should still be called, but return immediately
        captured.append((target_utc, warmup_sec, server_url))
        return

    monkeypatch.setattr(damai_app_v2, "_wait_until_utc", _fake_wait_until_utc)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "damai_app_v2",
            "--retries",
            "3",
            "--start-at",
            "2025-10-01 20:00:00",
            "--warmup-sec",
            "60",
        ],
    )

    exit_code = damai_app_v2.main()

    assert exit_code == 0
    assert len(DummyRunner.instances) == len(sample_configs)
    assert len(captured) == 1
    tgt, warm, server = captured[0]
    assert isinstance(tgt, datetime)
    assert warm == 60
    assert server == sample_configs[0].server_url