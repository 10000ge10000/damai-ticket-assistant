"""Unit tests for DamaiGUI CLI resolution helpers."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import damai_gui


class ResolveCliCommandTests(unittest.TestCase):
    """Tests for DamaiGUI._resolve_cli_command on Windows-like setups."""

    def setUp(self) -> None:  # noqa: D401
        self.gui = damai_gui.DamaiGUI.__new__(damai_gui.DamaiGUI)

    def test_uses_shutil_which_when_available(self) -> None:
        expected = "C:/appium/appium.cmd"
        with mock.patch.object(damai_gui.shutil, "which", return_value=expected):
            result = self.gui._resolve_cli_command("appium")
        self.assertEqual(result, expected)

    def test_searches_appdata_npm_directory(self) -> None:
        expected_path = Path("C:/Users/Test/AppData/Roaming/npm/appium.cmd")

        def fake_exists(path: Path) -> bool:
            return path == expected_path

        with (
            mock.patch.object(damai_gui.shutil, "which", return_value=None),
            mock.patch("damai_gui.os.name", "nt"),
            mock.patch.dict(
                damai_gui.os.environ,
                {"APPDATA": "C:/Users/Test/AppData/Roaming"},
                clear=True,
            ),
            mock.patch("damai_gui.Path.exists", lambda self: fake_exists(self)),
        ):
            result = self.gui._resolve_cli_command("appium")

        self.assertEqual(result, str(expected_path))

    def test_returns_none_when_not_found(self) -> None:
        with (
            mock.patch.object(damai_gui.shutil, "which", return_value=None),
            mock.patch("damai_gui.os.name", "nt"),
            mock.patch.dict(damai_gui.os.environ, {}, clear=True),
            mock.patch("damai_gui.Path.exists", lambda self: False),
        ):
            result = self.gui._resolve_cli_command("appium")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
