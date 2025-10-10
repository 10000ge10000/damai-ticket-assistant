import types

import pytest

import damai_gui


@pytest.fixture()
def gui_instance():
    gui = damai_gui.DamaiGUI()
    gui.root.withdraw()
    try:
        yield gui
    finally:
        gui.root.destroy()


def test_check_cli_dependency_success(monkeypatch, gui_instance):
    called = {}

    def fake_which(command):
        called["which"] = command
        return f"C:/tools/{command}.exe"

    def fake_run(_cmd, capture_output, text, timeout):
        called["run"] = True
        return types.SimpleNamespace(stdout="v1.2.3\n", stderr="", returncode=0)

    monkeypatch.setattr(damai_gui.shutil, "which", fake_which)
    monkeypatch.setattr(damai_gui.subprocess, "run", fake_run)

    ok, message = gui_instance._check_cli_dependency("node", ["--version"], "Node.js")

    assert ok is True
    assert message == "v1.2.3"
    assert called["which"] == "node"
    assert called["run"] is True


def test_check_cli_dependency_missing(monkeypatch, gui_instance):
    monkeypatch.setattr(damai_gui.shutil, "which", lambda _cmd: None)

    ok, message = gui_instance._check_cli_dependency("appium", ["-v"], "Appium CLI")

    assert ok is False
    assert "未找到" in message


def test_check_cli_dependency_error(monkeypatch, gui_instance):
    monkeypatch.setattr(damai_gui.shutil, "which", lambda _cmd: "C:/fake/appium.exe")

    def fake_run(_cmd, capture_output, text, timeout):
        raise RuntimeError("boom")

    monkeypatch.setattr(damai_gui.subprocess, "run", fake_run)

    ok, message = gui_instance._check_cli_dependency("appium", ["-v"], "Appium CLI")

    assert ok is False
    assert "失败" in message
