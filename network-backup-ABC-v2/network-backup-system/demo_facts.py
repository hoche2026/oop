import json
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
    """Thu thập facts của R1 và hiển thị dạng JSON."""
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

        facts = device.get_facts()
        print(json.dumps(facts, ensure_ascii=False, indent=2))

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
