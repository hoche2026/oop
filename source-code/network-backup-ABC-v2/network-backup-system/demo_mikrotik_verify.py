import json
from copy import deepcopy
from dataclasses import asdict
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

    checks = {
        "interfaces": {
            "ether1": {
                "ip_address": "192.168.241.24",
                "status": "up",
                "protocol": "up",
            },
        },
        "ping": {
            "target": "192.168.241.2",
            "source": "192.168.241.24",
            "min_success_percent": 100,
        },
    }

    try:
        device.connect()
        config = device.backup_config()

        result = device.verify_config(config, checks)
        print(json.dumps(
            asdict(result),
            indent=2,
            ensure_ascii=False,
        ))

        if not result.passed:
            raise RuntimeError("Xac minh trang thai hien tai chua dat.")

        wrong_checks = deepcopy(checks)
        wrong_checks.pop("ping")
        wrong_checks["interfaces"]["ether1"]["ip_address"] = "192.0.2.99"

        wrong_result = device.verify_config(config, wrong_checks)

        if wrong_result.passed:
            raise RuntimeError("Khong phat hien ky vong IP sai.")

        print("PASS: Phat hien ky vong IP sai.")
        print("PASS: XAC MINH MIKROTIK THANH CONG.")

    finally:
        device.disconnect()
        print("Da dong ket noi.")


if __name__ == "__main__":
    main()
