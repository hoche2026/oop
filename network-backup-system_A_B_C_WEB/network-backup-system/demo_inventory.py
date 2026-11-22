from pathlib import Path

from app.contracts import InventoryError
from app.inventory import InventoryManager


PROJECT_DIR = Path(__file__).resolve().parent


def main():
    """Kiểm tra đọc và lọc inventory bằng module chính thức."""
    manager = InventoryManager(
        PROJECT_DIR / "inventory" / "devices.yaml"
    )

    try:
        devices = manager.load()
        print(f"Tong so thiet bi: {len(devices)}")

        for device in devices:
            print(
                f"{device.name} | {device.host}:{device.port} "
                f"| {device.platform} | {device.role}"
            )

        routers = manager.filter(group="lab", role="router")
        print("Router trong nhom lab:", [d.name for d in routers])

        core_devices = manager.filter(tag="core")
        print("Thiet bi co tag core:", [d.name for d in core_devices])

        switches = manager.filter(role="switch")
        print("So switch:", len(switches))

    except InventoryError as error:
        print(f"Loi inventory: {error}")


if __name__ == "__main__":
    main()
