import os
from datetime import datetime
from pathlib import Path

from app.devices.factory import DeviceFactory
from app.inventory import InventoryManager


PROJECT_DIR = Path(__file__).resolve().parent

LINK_ADDRESSES = {
    "R1": "10.10.12.1",
    "R2": "10.10.12.2",
}


def apply_link(device_info):
    """Lưu bản trước thao tác rồi cấu hình cổng thử nghiệm."""
    device = DeviceFactory.create(device_info)

    try:
        device.connect()

        backup_dir = PROJECT_DIR / ".local_backups"
        backup_dir.mkdir(mode=0o700, exist_ok=True)
        os.chmod(backup_dir, 0o700)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = backup_dir / (
            f"{device.name}_before_link_{timestamp}.cfg"
        )

        config_before = device.backup_config()
        descriptor = os.open(
            backup_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(config_before)

        address = LINK_ADDRESSES[device.name]
        config_text = (
            "interface FastEthernet1/0\n"
            "description LINK_R1_R2\n"
            f"ip address {address} 255.255.255.252\n"
            "no shutdown\n"
            "exit\n"
        )

        result = device.push_config(config_text)
        print(
            f"{device.name}: da gui "
            f"{result['commands_sent']} lenh cau hinh."
        )
        print("Ban truoc thao tac:", backup_path.name)

    finally:
        device.disconnect()


def inspect_link(device_info):
    """Đọc lại trạng thái cổng sau khi đã cấu hình hai đầu."""
    device = DeviceFactory.create(device_info)

    try:
        device.connect()
        print(f"\nTRANG THAI {device.name}")
        print(device.send_command("show ip interface brief"))

    finally:
        device.disconnect()


def main():
    """Áp cấu hình đường nối trên đúng R1 và R2."""
    manager = InventoryManager(
        PROJECT_DIR / "inventory" / "devices.yaml"
    )
    devices = [
        device
        for device in manager.load()
        if device.name in LINK_ADDRESSES
    ]

    if {device.name for device in devices} != set(LINK_ADDRESSES):
        print("LOI: inventory phai co du R1 va R2.")
        return

    for device_info in devices:
        try:
            apply_link(device_info)
        except Exception as error:
            print(f"LOI {device_info.name}: {error}")
            print("Dung bai thu; kiem tra truoc khi chay lai.")
            return

    for device_info in devices:
        try:
            inspect_link(device_info)
        except Exception as error:
            print(f"LOI doc trang thai {device_info.name}: {error}")

    print("\nChua luu startup-config. Can kiem tra ping tiep.")


if __name__ == "__main__":
    main()
