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
        if item.name == "MT1"
    )
    device = DeviceFactory.create(info)

    try:
        device.connect()
        print("Lop thiet bi:", type(device).__name__)

        facts = device.get_facts()
        print(json.dumps(facts, indent=2, ensure_ascii=False))

        config = device.backup_config()
        print("So dong export:", len(config.splitlines()))
        print("PASS: KET NOI, DOC THONG TIN VA EXPORT MT1.")

    finally:
        device.disconnect()
        print("Da dong ket noi.")


if __name__ == "__main__":
    main()
