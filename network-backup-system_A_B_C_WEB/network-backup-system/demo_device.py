from pathlib import Path

from app.contracts import (
    DeviceCommandError,
    DeviceConnectionError,
    InventoryError,
)
from app.devices.factory import DeviceFactory
from app.inventory import InventoryManager


PROJECT_DIR = Path(__file__).resolve().parent


def main():
    """Kiểm tra inventory, Factory và lớp thiết bị Cisco."""
    device = None

    try:
        manager = InventoryManager(
            PROJECT_DIR / "inventory" / "devices.yaml"
        )
        device_info = next(
            (item for item in manager.load() if item.name == "R1"),
            None,
        )

        if device_info is None:
            raise InventoryError("Khong tim thay R1.")

        device = DeviceFactory.create(device_info)

        print("Lop thiet bi:", type(device).__name__)
        print(f"Dang ket noi {device.name} tai {device.host}...")

        device.connect()
        print("Ket noi thanh cong.")

        print(device.send_command("show ip interface brief"))

        config_text = device.backup_config()
        print("Da lay running-config.")
        print("So dong cau hinh:", len(config_text.splitlines()))

    except (
        InventoryError,
        DeviceConnectionError,
        DeviceCommandError,
    ) as error:
        print(f"LOI: {error}")

    finally:
        if device is not None:
            device.disconnect()
            print("Da dong ket noi.")


if __name__ == "__main__":
    main()
