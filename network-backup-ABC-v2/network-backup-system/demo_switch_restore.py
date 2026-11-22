import json
import os
from pathlib import Path
from uuid import uuid4

from app.inventory import InventoryManager
from app.devices.factory import DeviceFactory


PROJECT_DIR = Path(__file__).resolve().parent
MARKER = "THU_KHOI_PHUC_SW1_PYTHON"


def main():
    inventory = InventoryManager(
        PROJECT_DIR / "inventory" / "devices.yaml"
    )
    info = next(
        item for item in inventory.load()
        if item.name == "SW1"
    )
    device = DeviceFactory.create(info)
    snapshot_path = None
    change_started = False

    try:
        device.connect()

        before_interface = device.send_command(
            "show running-config interface Ethernet0/3"
        )

        if MARKER in before_interface:
            raise RuntimeError(
                "Mo ta thu da ton tai. Dung de kiem tra truoc."
            )

        baseline = device.backup_config()

        backup_dir = PROJECT_DIR / ".local_backups"
        backup_dir.mkdir(mode=0o700, exist_ok=True)
        backup_dir.chmod(0o700)

        snapshot_path = backup_dir / (
            f"SW1_before_restore_{uuid4().hex}.cfg"
        )
        descriptor = os.open(
            snapshot_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )

        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(baseline)

        print("Da luu ban sao:", snapshot_path)

        change_started = True
        device.push_config(
            "interface Ethernet0/3\n"
            f" description {MARKER}\n"
            " exit\n"
        )

        changed = device.send_command(
            "show running-config interface Ethernet0/3"
        )

        if MARKER not in changed:
            raise RuntimeError("Chua xac nhan mo ta thu vua them.")

        print("Da xac nhan mo ta thu ton tai.")
        print("Dang chuyen file va khoi phuc SW1...")

        result = device.restore_config(baseline)
        print(json.dumps(result, indent=2, ensure_ascii=False))

        device.disconnect()
        device.connect()
        print("Da ket noi lai SW1.")

        after_interface = device.send_command(
            "show running-config interface Ethernet0/3"
        )

        if MARKER in after_interface:
            raise RuntimeError("Mo ta thu van ton tai sau khoi phuc.")

        print("PASS: Mo ta thu da bien mat.")

        checks = {
            "interfaces": {
                "Vlan1": {
                    "ip_address": "192.168.241.23",
                    "status": "up",
                    "protocol": "up",
                },
            },
            "ping": {
                "target": "192.168.241.131",
                "source": "192.168.241.23",
                "min_success_percent": 100,
            },
        }

        verification = device.verify_config(baseline, checks)

        for detail in verification.details:
            print(detail)

        if not verification.passed:
            raise RuntimeError("Xac minh sau khoi phuc chua dat.")

        print("PASS: KHOI PHUC VA XAC MINH SW1 THANH CONG.")
        print("Chua luu startup-config.")

    except Exception:
        if change_started:
            print("Dung tai day va kiem tra console SW1.")
            print("Ban sao truoc thu nghiem:", snapshot_path)
        raise

    finally:
        device.disconnect()
        print("Da dong ket noi.")


if __name__ == "__main__":
    main()
