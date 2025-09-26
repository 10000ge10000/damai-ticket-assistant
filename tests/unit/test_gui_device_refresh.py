import pytest

import damai_gui


@pytest.fixture
def gui_appium_ready(monkeypatch):
    monkeypatch.setattr(damai_gui, "APPIUM_AVAILABLE", True)
    monkeypatch.setattr(damai_gui, "parse_adb_devices", lambda output: [], raising=False)
    gui = damai_gui.DamaiGUI()
    gui.root.withdraw()
    try:
        yield gui
    finally:
        gui.root.destroy()


@pytest.fixture
def gui_appium_missing(monkeypatch):
    monkeypatch.setattr(damai_gui, "APPIUM_AVAILABLE", False)
    monkeypatch.setattr(damai_gui, "parse_adb_devices", None, raising=False)
    gui = damai_gui.DamaiGUI()
    gui.root.withdraw()
    try:
        yield gui
    finally:
        gui.root.destroy()


def test_update_device_status_success(gui_appium_ready):
    gui = gui_appium_ready
    gui.app_detected_devices = ["emulator-5554", "device-1234"]

    gui._update_device_status_from_result(True)

    assert "已检测到 2 台可用设备" in gui.app_device_status_var.get()
    assert str(gui.app_device_status_label.cget("foreground")) == "green"

    detail_text = gui.app_device_detail_var.get()
    assert "emulator-5554" in detail_text
    assert "device-1234" in detail_text
    assert str(gui.app_device_detail_label.cget("foreground")) == "green"


def test_update_device_status_no_devices(gui_appium_ready):
    gui = gui_appium_ready
    gui.app_detected_devices = []

    gui._update_device_status_from_result(False)

    assert gui.app_device_status_var.get() == "未检测到可用设备"
    assert str(gui.app_device_status_label.cget("foreground")) == "orange"
    assert "USB" in gui.app_device_detail_var.get()
    assert str(gui.app_device_detail_label.cget("foreground")) == "orange"


def test_update_device_status_appium_missing(gui_appium_missing):
    gui = gui_appium_missing

    gui._update_device_status_from_result(True)

    assert gui.app_device_status_var.get() == "无法检测设备"
    assert str(gui.app_device_status_label.cget("foreground")) == "red"
    assert "Appium" in gui.app_device_detail_var.get()
    assert str(gui.app_device_refresh_btn["state"]) == "disabled"
