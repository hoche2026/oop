from pathlib import Path

from app.contracts import (
    DeviceCommandError,
    DeviceConnectionError,
    InventoryError,
)
from app.devices.factory import DeviceFactory
from app.inventory import InventoryManager


PROJECT_DIR = Path(__file__).resolve().parent


def inspect_device(device_info):
    """Kiểm tra một thiết bị; luôn đóng kết nối sau thao tác."""
    device = None

    try:
        device = DeviceFactory.create(device_info)
        device.connect()

        facts = device.get_facts()
        config_text = device.backup_config()

        print(f"\nTHIET BI: {device.name}")
        print("IP:", device.host)
        print("Lop:", type(device).__name__)
        print("Hostname:", facts["hostname"])
        print("IOS:", facts["os_version"])
        print("So cong:", len(facts["interfaces"]))
        print("So dong cau hinh:", len(config_text.splitlines()))

        sections = (
            "routing_table",
            "arp_table",
            "cdp_neighbors",
            "cpu",
            "memory",
        )
        for section in sections:
            print(f"{section}: {facts[section]['status']}")

        return True

    except (
        InventoryError,
        DeviceConnectionError,
        DeviceCommandError,
    ) as error:
        print(f"\nLOI {device_info.name}: {error}")
        return False

    finally:
        if device is not None:
            device.disconnect()


def main():
    """Thu thập lần lượt trên các router trong nhóm lab."""
    manager = InventoryManager(
        PROJECT_DIR / "inventory" / "devices.yaml"
    )

    try:
        devices = manager.filter(group="lab", role="router")
    except InventoryError as error:
        print(f"LOI inventory: {error}")
        return

    if not devices:
        print("Khong co router trong nhom lab.")
        return

    success_count = 0

    for device_info in devices:
        if inspect_device(device_info):
            success_count += 1

    print(
        f"\nKet noi va thu thap hoan thanh: "
        f"{success_count}/{len(devices)} thiet bi."
    )
    print("Xem status tung muc de biet chat luong du lieu.")


if __name__ == "__main__":
    main()
