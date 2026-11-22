from pathlib import Path

from app.contracts import (
    DeviceCommandError,
    DeviceConnectionError,
    InventoryError,
)
from app.devices.factory import DeviceFactory
from app.inventory import InventoryManager


PROJECT_DIR = Path(__file__).resolve().parent

COMMANDS = (
    ("BANG DINH TUYEN", "show ip route"),
    ("BANG ARP", "show ip arp"),
    ("LANG GIENG CDP", "show cdp neighbors"),
    ("CPU", "show processes cpu | include CPU utilization"),
    ("BO NHO", "show memory statistics"),
)


def main():
    """Thu thập dữ liệu thực tế để kiểm tra trước khi chuẩn hóa."""
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
        device.connect()
        print(f"Da ket noi {device.name} tai {device.host}")

        for title, command in COMMANDS:
            print(f"\n=== {title} ===")
            print(f"Lenh: {command}")

            try:
                output = device.send_command(command)
                print(output if output.strip() else "(Khong co noi dung)")
            except DeviceCommandError as error:
                print(f"LOI: {error}")

    except (InventoryError, DeviceConnectionError) as error:
        print(f"LOI: {error}")

    finally:
        if device is not None:
            device.disconnect()
            print("\nDa dong ket noi.")


if __name__ == "__main__":
    main()
