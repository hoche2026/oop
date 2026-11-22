import os
import unittest
from unittest.mock import MagicMock, patch

from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)

from app.contracts import (
    DeviceConnectionError,
    DeviceInfo,
    InventoryError,
)
from app.devices.factory import DeviceFactory


class DeviceConnectionTests(unittest.TestCase):
    CASES = (
        (
            "cisco_ios",
            "router",
            "CiscoIOSDevice",
            "app.devices.cisco_ios.ConnectHandler",
        ),
        (
            "cisco_ios",
            "switch",
            "CiscoIOSSwitchDevice",
            "app.devices.cisco_ios.ConnectHandler",
        ),
        (
            "mikrotik_routeros",
            "router",
            "MikroTikDevice",
            "app.devices.mikrotik.ConnectHandler",
        ),
    )

    def setUp(self):
        # Khong doc .env that trong cac bai thu.
        self.dotenv_patch = patch(
            "app.devices.base.load_dotenv"
        )
        self.dotenv_patch.start()
        self.addCleanup(self.dotenv_patch.stop)

        self.env_patch = patch.dict(
            os.environ,
            {
                "TEST_A_USERNAME": "test_user",
                "TEST_A_PASSWORD": "test_password",
                "TEST_A_SECRET": "test_secret",
            },
            clear=True,
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def make_info(self, platform="cisco_ios", role="router"):
        return DeviceInfo(
            name="TEST_DEVICE",
            host="192.0.2.10",
            port=22,
            platform=platform,
            group="test",
            role=role,
            tags=["offline"],
            credential_profile="TEST_A",
        )

    def test_factory_selects_expected_classes(self):
        for platform, role, class_name, _ in self.CASES:
            with self.subTest(platform=platform, role=role):
                device = DeviceFactory.create(
                    self.make_info(platform, role)
                )
                self.assertEqual(
                    type(device).__name__,
                    class_name,
                )

    def test_factory_rejects_unknown_platform(self):
        with self.assertRaises(InventoryError):
            DeviceFactory.create(
                self.make_info(platform="unsupported_lab")
            )

    def test_missing_credentials_are_rejected(self):
        os.environ.pop("TEST_A_PASSWORD")

        with self.assertRaises(DeviceConnectionError):
            DeviceFactory.create(self.make_info())

    def test_authentication_errors_are_wrapped(self):
        for platform, role, _, target in self.CASES:
            with self.subTest(platform=platform, role=role):
                device = DeviceFactory.create(
                    self.make_info(platform, role)
                )

                with patch(
                    target,
                    side_effect=NetmikoAuthenticationException(
                        "Simulated authentication failure"
                    ),
                ) as connector:
                    with self.assertRaises(DeviceConnectionError):
                        device.connect()

                    connector.assert_called_once()

                self.assertIsNone(device._connection)
                device.disconnect()

    def test_timeouts_are_wrapped(self):
        for platform, role, _, target in self.CASES:
            with self.subTest(platform=platform, role=role):
                device = DeviceFactory.create(
                    self.make_info(platform, role)
                )

                with patch(
                    target,
                    side_effect=NetmikoTimeoutException(
                        "Simulated timeout"
                    ),
                ):
                    with self.assertRaises(DeviceConnectionError):
                        device.connect()

                self.assertIsNone(device._connection)
                device.disconnect()

    def test_connection_lifecycle_and_host_key_checking(self):
        for platform, role, _, target in self.CASES:
            with self.subTest(platform=platform, role=role):
                device = DeviceFactory.create(
                    self.make_info(platform, role)
                )
                connection = MagicMock()

                with patch(target, return_value=connection) as connector:
                    device.connect()
                    device.connect()

                    # Khong tao them ket noi khi doi tuong dang ket noi.
                    connector.assert_called_once()

                    kwargs = connector.call_args.kwargs
                    self.assertTrue(kwargs["ssh_strict"])
                    self.assertTrue(kwargs["system_host_keys"])

                    if platform == "cisco_ios":
                        connection.enable.assert_called_once()
                    else:
                        connection.enable.assert_not_called()

                    device.disconnect()
                    device.disconnect()

                    connection.disconnect.assert_called_once()
                    self.assertIsNone(device._connection)

    def test_commands_require_connection(self):
        for platform, role, _, _ in self.CASES:
            with self.subTest(platform=platform, role=role):
                device = DeviceFactory.create(
                    self.make_info(platform, role)
                )

                with self.assertRaises(DeviceConnectionError):
                    device.send_command("test command")


if __name__ == "__main__":
    unittest.main()
