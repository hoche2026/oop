import json
from pathlib import Path

from app.inventory import InventoryManager
from app.devices.factory import DeviceFactory


PROJECT_DIR = Path(__file__).resolve().parent


def main():
    inventory = InventoryManager(
        PROJECT_DIR / "inventory" / "devices.yaml"
    )
    info = next(
        item for item in inventory.load()
        if item.name == "SW1"
    )
    device = DeviceFactory.create(info)

    try:
        device.connect()
        print("Lop thiet bi:", type(device).__name__)

        facts = device.get_facts()

        for section in ("vlans", "mac_table"):
            print(f"\n=== {section.upper()} ===")
            print(json.dumps(
                facts[section],
                indent=2,
                ensure_ascii=False,
            ))

        vlan_ok = facts["vlans"]["status"] == "ok"
        mac_ok = facts["mac_table"]["status"] in {"ok", "empty"}

        if vlan_ok and mac_ok:
            print("\nPASS: THU THAP VLAN VA MAC CO CAU TRUC.")
        else:
            print("\nCHUA DAT: xem status va error o tren.")

    finally:
        device.disconnect()
        print("Da dong ket noi.")


if __name__ == "__main__":
    main()
