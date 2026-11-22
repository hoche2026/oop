import json
import os
from pathlib import Path
from uuid import uuid4

from app.inventory import InventoryManager
from app.devices.factory import DeviceFactory


PROJECT_DIR = Path(__file__).resolve().parent
BRIDGE = "oop-python-restore"


def main():
    inventory = InventoryManager(
        PROJECT_DIR / "inventory" / "devices.yaml"
    )
    info = next(
        item for item in inventory.load()
        if item.name == "MT1"
    )
    device = DeviceFactory.create(info)
    snapshot_path = None
    changed = False

    count_command = (
        f':put [:len [/interface bridge find where name="{BRIDGE}"]]'
    )

    try:
        device.connect()

        if int(device.send_command(count_command).strip()) != 0:
            raise RuntimeError("Bridge thu da ton tai; dung kiem tra.")

        point_text = device.create_restore_point()

        folder = PROJECT_DIR / ".local_backups"
        folder.mkdir(mode=0o700, exist_ok=True)
        folder.chmod(0o700)
        snapshot_path = folder / (
            f"MT1_before_restore_{uuid4().hex}.restorepoint.json"
        )

        descriptor = os.open(
            snapshot_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(point_text)

        print("Da luu ban sao:", snapshot_path)

        changed = True
        device.push_config(
            f'/interface bridge add name="{BRIDGE}" '
            'protocol-mode=none comment="THU_RESTORE_PYTHON"'
        )

        if int(device.send_command(count_command).strip()) != 1:
            raise RuntimeError("Chua xac nhan bridge vua tao.")

        print("Da tao bridge thu.")
        print("Dang khoi phuc. MT1 se reboot; cho SSH tro lai...")

        result = device.restore_config(point_text)
        print(json.dumps(result, indent=2))

        if int(device.send_command(count_command).strip()) != 0:
            raise RuntimeError("Bridge thu van ton tai sau khoi phuc.")

        print("PASS: Bridge thu da bien mat.")

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
        verification = device.verify_config("", checks)

        for detail in verification.details:
            print(detail)

        if not verification.passed:
            raise RuntimeError("Xac minh sau khoi phuc chua dat.")

        print("PASS: KHOI PHUC VA XAC MINH MIKROTIK THANH CONG.")

    except Exception:
        if changed:
            print("Dung tai day, kiem tra console MT1 truoc khi chay lai.")
            print("Ban sao:", snapshot_path)
        raise

    finally:
        device.disconnect()
        print("Da dong ket noi.")


if __name__ == "__main__":
    main()
