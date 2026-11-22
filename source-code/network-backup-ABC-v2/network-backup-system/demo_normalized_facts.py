from pathlib import Path

from app.inventory import InventoryManager
from app.devices.factory import DeviceFactory


PROJECT_DIR = Path(__file__).resolve().parent


def main():
    inventory = InventoryManager(
        PROJECT_DIR / "inventory" / "devices.yaml"
    )

    for info in inventory.load():
        device = None

        try:
            device = DeviceFactory.create(info)
            device.connect()
            facts = device.get_normalized_facts()

            cpu = facts["cpu"]
            memory = facts["memory"]
            cpu_data = cpu.get("data") or {}
            memory_data = memory.get("data") or {}

            print(f"\n{info.name}")
            print(
                "CPU:",
                cpu["status"],
                "| %",
                cpu_data.get("usage_percent"),
            )
            print(
                "RAM:",
                memory["status"],
                "| %",
                memory_data.get("used_percent"),
                "| scope:",
                memory_data.get("scope"),
            )

        except Exception as error:
            print(f"{info.name}: ERROR {type(error).__name__}")

        finally:
            if device is not None:
                device.disconnect()


if __name__ == "__main__":
    main()
