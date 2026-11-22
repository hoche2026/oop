from pathlib import Path

from app.contracts import DeviceCommandError
from app.inventory import InventoryManager
from app.devices.factory import DeviceFactory


PROJECT_DIR = Path(__file__).resolve().parent


def main():
    inventory = InventoryManager(
        PROJECT_DIR / "inventory" / "devices.yaml"
    )
    matches = [
        info
        for info in inventory.load()
        if info.name == "SW1"
    ]

    if len(matches) != 1:
        raise RuntimeError("Inventory phai co dung mot SW1.")

    device = DeviceFactory.create(matches[0])

    try:
        device.connect()
        print("Da ket noi SW1.")
        print("Lop thiet bi:", type(device).__name__)

        facts = device.get_facts()

        print("Hostname:", facts.get("hostname"))
        print("IOS:", facts.get("os_version"))
        print("So interface:", len(facts.get("interfaces", [])))

        commands = [
            ("TRANG THAI CONG", "show ip interface brief"),
            ("DANH SACH VLAN", "show vlan brief"),
            ("BANG MAC", "show mac address-table"),
        ]

        failed = []

        for label, command in commands:
            print(f"\n=== {label} ===")

            try:
                print(device.send_command(command))
            except DeviceCommandError as error:
                failed.append(command)
                print(f"LOI: {error}")

        config = device.backup_config()
        print("\nSo dong running-config:", len(config.splitlines()))

        if failed:
            print("Lenh can kiem tra lai:", failed)
        else:
            print("PASS: DOC DU LIEU SWITCH THANH CONG.")

    finally:
        device.disconnect()
        print("Da dong ket noi.")


if __name__ == "__main__":
    main()
