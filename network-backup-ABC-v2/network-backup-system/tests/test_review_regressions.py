import os
import unittest
from unittest.mock import MagicMock, patch

from app.contracts import DeviceCommandError, DeviceConnectionError, DeviceInfo
from app.devices.factory import DeviceFactory
from app.normalization import normalize_facts


class ReviewRegressionTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {
            "REVIEW_USERNAME": "test", "REVIEW_PASSWORD": "test",
        }, clear=True)
        env.start()
        self.addCleanup(env.stop)
        dotenv = patch("app.devices.base.load_dotenv")
        dotenv.start()
        self.addCleanup(dotenv.stop)

    def device(self, platform):
        return DeviceFactory.create(DeviceInfo(
            "TEST", "192.0.2.1", 22, platform,
            "test", "router", [], "REVIEW",
        ))

    def test_dead_connections_are_replaced(self):
        for platform, module in (
            ("cisco_ios", "cisco_ios"),
            ("mikrotik_routeros", "mikrotik"),
        ):
            with self.subTest(platform=platform):
                device = self.device(platform)
                stale = MagicMock()
                stale.is_alive.return_value = False
                device._connection = stale
                fresh = MagicMock()
                with patch(f"app.devices.{module}.ConnectHandler", return_value=fresh) as factory:
                    device.connect()
                factory.assert_called_once()
                stale.disconnect.assert_called_once()
                self.assertIs(device._connection, fresh)
                device.disconnect()

    def test_cleanup_does_not_mask_enable_failure(self):
        device = self.device("cisco_ios")
        connection = MagicMock()
        connection.enable.side_effect = ValueError("enable failed")
        connection.disconnect.side_effect = RuntimeError("cleanup failed")
        with patch("app.devices.cisco_ios.ConnectHandler", return_value=connection):
            with self.assertRaises(DeviceConnectionError) as raised:
                device.connect()
        self.assertIsInstance(raised.exception.__cause__, ValueError)
        self.assertIsNone(device._connection)

    def test_health_check_and_cleanup_failure_allow_reconnect(self):
        for platform, module in (
            ("cisco_ios", "cisco_ios"),
            ("mikrotik_routeros", "mikrotik"),
        ):
            with self.subTest(platform=platform):
                device = self.device(platform)
                stale = MagicMock()
                stale.is_alive.side_effect = OSError("dead transport")
                stale.disconnect.side_effect = OSError("cleanup failed")
                device._connection = stale
                fresh = MagicMock()
                with patch(f"app.devices.{module}.ConnectHandler", return_value=fresh):
                    device.connect()
                self.assertIs(device._connection, fresh)
                device.disconnect()

    def test_cisco_cli_error_is_rejected(self):
        device = self.device("cisco_ios")
        device._connection = MagicMock()
        device._connection.send_command.return_value = "% Error opening file"
        with self.assertRaises(DeviceCommandError):
            device.send_command("show test")
        device.disconnect()

    def test_normal_output_is_unchanged(self):
        device = self.device("cisco_ios")
        device._connection = MagicMock()
        output = "CPU utilization for five seconds: 5%/1%"
        device._connection.send_command.return_value = output
        self.assertEqual(device.send_command("show test"), output)
        device.disconnect()

    def test_malformed_memory_does_not_destroy_other_sections(self):
        original = {
            "memory": {"status": "ok", "data": {"pools": [None]}, "error": None},
            "cpu": {"status": "ok", "data": {"usage_percent": 5, "valid": True}, "error": None},
        }
        result = normalize_facts(original)
        self.assertEqual(result["memory"]["status"], "error")
        self.assertEqual(result["cpu"]["data"]["usage_percent"], 5)
        self.assertEqual(original["memory"]["data"]["pools"], [None])

    def test_non_dictionary_section_is_reported(self):
        result = normalize_facts({"memory": [], "routing_table": "bad"})
        self.assertEqual(result["memory"]["status"], "error")
        self.assertEqual(result["routing_table"]["status"], "error")


if __name__ == "__main__":
    unittest.main()
