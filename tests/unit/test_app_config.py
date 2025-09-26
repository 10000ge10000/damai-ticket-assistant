import json

import pytest

from damai_appium.config import (
    AppTicketConfig,
    AdbDeviceInfo,
    _clean_users,
    _normalise_server_url,
    _strip_jsonc,
    parse_adb_devices,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("http://127.0.0.1:4723", "http://127.0.0.1:4723"),
        ("https://example.com", "https://example.com"),
        (" 127.0.0.1:4723 ", "http://127.0.0.1:4723"),
        ("", ""),
    ],
)
def test_normalise_server_url(raw, expected):
    assert _normalise_server_url(raw) == expected


def test_strip_jsonc_removes_comments():
    content = """
    {
        // single line comment
        "server_url": "127.0.0.1:4723", /* inline */
        "users": ["Alice", "Bob"]
    }
    """
    cleaned = _strip_jsonc(content)
    assert "//" not in cleaned
    assert "/*" not in cleaned
    loaded = json.loads(cleaned)
    assert loaded["server_url"] == "127.0.0.1:4723"


def test_clean_users_filters_empty_and_whitespace():
    users = [" Alice ", "", None, "Bob", "  "]
    assert _clean_users(users) == ["Alice", "Bob"]


def test_app_ticket_config_validation_errors():
    with pytest.raises(ValueError):
        AppTicketConfig(server_url="", users=[])

    with pytest.raises(ValueError):
        AppTicketConfig(server_url="http://localhost", price_index=-1)


def test_app_ticket_config_desired_capabilities_merge():
    config = AppTicketConfig(
        server_url="http://127.0.0.1:4723",
        device_caps={
            "deviceName": "Pixel",
            "automationName": "Appium",
            "customKey": "custom-value",
        },
    )

    caps = config.desired_capabilities
    assert caps["platformName"] == "Android"
    assert caps["deviceName"] == "Pixel"
    assert caps["automationName"] == "Appium"
    assert caps["customKey"] == "custom-value"


def test_app_ticket_config_from_mapping_types():
    payload = {
        "server_url": "https://example.com",
        "users": ["  Alice  ", "Bob", ""],
        "price_index": 2,
        "if_commit_order": 0,
        "wait_timeout": "3.5",
        "retry_delay": 4,
    }

    config = AppTicketConfig.from_mapping(payload)
    assert config.server_url == "https://example.com"
    assert config.users == ["Alice", "Bob"]
    assert config.price_index == 2
    assert config.if_commit_order is False
    assert config.wait_timeout == 3.5
    assert config.retry_delay == 4.0


def test_app_ticket_config_load_from_jsonc(tmp_path):
    config_path = tmp_path / "config.jsonc"
    config_path.write_text(
        """
        {
            // server configuration
            "server_url": "127.0.0.1:4723",
            "users": ["  Alice  ", "Bob", ""],
            "price": "380元",
            "if_commit_order": false,
            "device_caps": {"deviceName": "Pixel"}
        }
        """,
        encoding="utf-8",
    )

    config = AppTicketConfig.load(config_path)
    assert config.server_url == "http://127.0.0.1:4723"
    assert config.users == ["Alice", "Bob"]
    assert config.price == "380元"
    assert config.if_commit_order is False
    assert config.device_caps["deviceName"] == "Pixel"


def test_parse_adb_devices_extracts_ready_device():
    output = """List of devices attached
ZY2246K6H9 device product:walleye model:Pixel_2 device:walleye transport_id:1

"""

    devices = parse_adb_devices(output)
    assert len(devices) == 1

    device = devices[0]
    assert isinstance(device, AdbDeviceInfo)
    assert device.serial == "ZY2246K6H9"
    assert device.status == "device"
    assert device.is_ready
    label = device.describe()
    assert "Pixel_2" in label and "ZY2246K6H9" in label


def test_parse_adb_devices_handles_offline_device_and_noise():
    output = """List of devices attached
emulator-5554 offline
* daemon not running. starting it now on port 5037 *

"""

    devices = parse_adb_devices(output)
    assert len(devices) == 1

    device = devices[0]
    assert device.serial == "emulator-5554"
    assert device.status == "offline"
    assert device.is_ready is False
    assert device.describe() == "emulator-5554"


def test_parse_adb_devices_empty_output():
    assert parse_adb_devices("") == []
