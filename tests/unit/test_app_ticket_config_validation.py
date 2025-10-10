import json

import pytest

from damai_appium import AppTicketConfig, ConfigValidationError
from damai_appium.config import (
    AdbDeviceInfo,
    _clean_users,
    _normalise_server_url,
    _resolve_config_path,
    _strip_jsonc,
    parse_adb_devices,
)


def test_from_mapping_valid_payload_normalises_fields():
    payload = {
        "serverUrl": "127.0.0.1:4723/wd/hub",
        "users": ["  Alice  ", "Bob", ""],
        "ifCommitOrder": "false",
        "waitTimeout": "5",
        "retryDelay": 3.5,
        "deviceCaps": {"udid": "device123"},
    }

    config = AppTicketConfig.from_mapping(payload)

    assert config.server_url == "http://127.0.0.1:4723/wd/hub"
    assert config.users == ["Alice", "Bob"]
    assert config.if_commit_order is False
    assert config.wait_timeout == pytest.approx(5.0)
    assert config.retry_delay == pytest.approx(3.5)
    assert config.device_caps["udid"] == "device123"


@pytest.mark.parametrize(
    "payload, expected_error_field",
    [
        ({}, "server_url"),
        ({"server_url": "http://localhost", "retry_delay": -1}, "retry_delay"),
        ("invalid", "root"),
    ],
)
def test_from_mapping_invalid_payload_raises(payload, expected_error_field):
    with pytest.raises(ConfigValidationError) as excinfo:
        AppTicketConfig.from_mapping(payload)

    error_messages = excinfo.value.errors
    assert any(expected_error_field in message for message in error_messages)
    assert "配置校验失败" in str(excinfo.value)


def test_load_wraps_validation_error(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"retry_delay": -5}), encoding="utf-8")

    with pytest.raises(ConfigValidationError) as excinfo:
        AppTicketConfig.load(config_path)

    assert excinfo.value.message.startswith(f"{config_path.name} 配置校验失败")
    assert any("retry_delay" in message for message in excinfo.value.errors)


def test_from_mapping_supports_aliases_and_defaults():
    payload = {
        "server_url": "http://localhost:4723/wd/hub",
        "priceIndex": "2",
        "waitTimeout": "",
        "retryDelay": "4.5",
        "deviceCaps": {"deviceName": "Pixel", "automationName": "UiAutomator3"},
        "keyword": "  hello  ",
        "price": "  100 ",
    }

    config = AppTicketConfig.from_mapping(payload)

    assert config.price_index == 2
    assert config.wait_timeout == pytest.approx(2.0)
    assert config.retry_delay == pytest.approx(4.5)
    assert config.device_caps["automationName"] == "UiAutomator3"
    assert config.device_caps["deviceName"] == "Pixel"
    assert config.keyword == "hello"
    assert config.price == "100"


def test_from_mapping_multi_generates_configs_for_overrides():
    payload = {
        "server_url": "http://localhost:4723/wd/hub",
        "keyword": "base",
        "users": ["alice"],
        "device_caps": {"deviceName": "Base", "udid": "base-udid"},
        "devices": [
            {
                "device_caps": {"deviceName": "Override", "udid": "override-udid"},
                "keyword": "override",
                "if_commit_order": False,
                "retry_delay": 5,
            }
        ],
    }

    configs = AppTicketConfig.from_mapping_multi(payload)

    assert len(configs) == 2
    base_config, override_config = configs
    assert base_config.keyword == "base"
    assert base_config.device_caps["deviceName"] == "Base"
    assert base_config.if_commit_order is True

    assert override_config.keyword == "override"
    assert override_config.if_commit_order is False
    assert override_config.retry_delay == pytest.approx(5.0)
    assert override_config.device_caps["udid"] == "override-udid"
    assert override_config.device_caps["deviceName"] == "Override"
    # 未覆盖的字段沿用基准配置
    assert override_config.users == ["alice"]


def test_from_mapping_multi_invalid_override_reports_index():
    payload = {
        "server_url": "http://localhost",
        "devices": [
            {
                "retry_delay": -1,
            }
        ],
    }

    with pytest.raises(ConfigValidationError) as excinfo:
        AppTicketConfig.from_mapping_multi(payload)

    assert excinfo.value.message.startswith("配置校验失败")
    assert any("retry_delay" in message for message in excinfo.value.errors)


def test_from_mapping_invalid_users_type_error():
    payload = {"server_url": "http://localhost", "users": 123}

    with pytest.raises(ConfigValidationError) as excinfo:
        AppTicketConfig.from_mapping(payload)

    assert any("users" in message for message in excinfo.value.errors)


def test_from_mapping_invalid_price_index():
    payload = {"server_url": "http://localhost", "price_index": -1}

    with pytest.raises(ConfigValidationError) as excinfo:
        AppTicketConfig.from_mapping(payload)

    assert any("票价索引" in message for message in excinfo.value.errors)


def test_from_mapping_invalid_device_caps_type():
    payload = {"server_url": "http://localhost", "device_caps": 42}

    with pytest.raises(ConfigValidationError) as excinfo:
        AppTicketConfig.from_mapping(payload)

    assert any("device_caps" in message for message in excinfo.value.errors)


def test_from_mapping_invalid_wait_timeout_format():
    payload = {"server_url": "http://localhost", "wait_timeout": "abc"}

    with pytest.raises(ConfigValidationError) as excinfo:
        AppTicketConfig.from_mapping(payload)

    assert any("wait_timeout" in message for message in excinfo.value.errors)


def test_desired_capabilities_override_defaults():
    config = AppTicketConfig(
        server_url="http://localhost",
        device_caps={
            "deviceName": "Custom",
            "udid": "abc123",
            "automationName": "UiAutomator3",
        },
    )

    caps = config.desired_capabilities

    assert caps["deviceName"] == "Custom"
    assert caps["automationName"] == "UiAutomator3"
    assert caps["udid"] == "abc123"
    assert caps["platformName"] == "Android"


def test_strip_jsonc_removes_comments():
    content = '{"a": 1, // comment\n "b": 2 /* another */}'

    assert json.loads(_strip_jsonc(content)) == {"a": 1, "b": 2}


def test_parse_adb_devices_parses_entries():
    raw_output = """
    List of devices attached
    emulator-5554\tdevice product:sdk_gphone model:sdk_gphone_x86 transport_id:1
    * daemon not running; starting now at tcp:5037
    deadbeef\toffline
    """

    devices = parse_adb_devices(raw_output)

    assert len(devices) == 2
    assert devices[0].serial == "emulator-5554"
    assert devices[0].is_ready is True
    assert devices[0].properties["model"] == "sdk_gphone_x86"
    assert devices[1].is_ready is False


def test_normalise_server_url_variants():
    assert _normalise_server_url(" example.com ") == "http://example.com"
    assert _normalise_server_url("https://secure") == "https://secure"
    assert _normalise_server_url(" ") == ""


def test_clean_users_filters_values():
    users = _clean_users([" Alice ", None, 123, "", "Bob"])
    assert users == ["Alice", "123", "Bob"]


def test_config_validation_error_formats_message():
    error = ConfigValidationError(["server_url: 不能为空", "users: 至少需要 1 个"])

    message = str(error)
    assert "配置校验失败" in message
    assert "- server_url: 不能为空" in message
    assert error.errors == ["server_url: 不能为空", "users: 至少需要 1 个"]


def test_adb_device_describe_combines_known_properties():
    device = AdbDeviceInfo(
        serial="abc123",
        status="device",
        properties={"model": "Pixel", "device": "pixel", "transport_id": "9"},
    )

    description = device.describe()

    assert "Pixel" in description
    assert "transport:9" in description


def test_resolve_config_path_handles_str_and_missing(tmp_path):
    config_file = tmp_path / "custom.json"
    config_file.write_text("{}", encoding="utf-8")

    resolved = _resolve_config_path(str(config_file))
    assert resolved == config_file

    with pytest.raises(FileNotFoundError):
        _resolve_config_path(tmp_path / "does_not_exist.json")


def test_app_ticket_config_endpoint_property():
    config = AppTicketConfig(server_url="localhost:4723")

    assert config.endpoint == "http://localhost:4723"