import json
import os
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.inventory import InventoryManager
from app.devices.factory import DeviceFactory


PROJECT_DIR = Path(__file__).resolve().parent


def has_loopback99(output):
    return re.search(
        r"^\s*Loopback99\s+",
        output,
        flags=re.MULTILINE,
    ) is not None


def main():
    inventory = InventoryManager(
        PROJECT_DIR / "inventory" / "devices.yaml"
    )
    matches = [
        info
        for info in inventory.load()
        if info.name == "R1"
    ]

    if len(matches) != 1:
        raise RuntimeError("Inventory phai co dung mot thiet bi R1.")

    device = DeviceFactory.create(matches[0])
    snapshot_path = None
    change_started = False
    completed = False

    checks = {
        "interfaces": {
            "FastEthernet0/0": {
                "ip_address": "192.168.241.21",
                "status": "up",
                "protocol": "up",
            },
            "FastEthernet1/0": {
                "ip_address": "10.10.12.1",
                "status": "up",
                "protocol": "up",
            },
        },
        "ping": {
            "target": "10.10.12.2",
            "source": "10.10.12.1",
            "min_success_percent": 100,
        },
    }

    try:
        device.connect()
        print("Da ket noi R1.")

        interfaces = device.send_command(
            "show ip interface brief"
        )

        if has_loopback99(interfaces):
            raise RuntimeError(
                "Loopback99 da ton tai. Dung thu de tranh "
                "tac dong len cau hinh co san."
            )

        baseline = device.backup_config()
        before = device.verify_config(baseline, checks)

        if not before.passed:
            print(json.dumps(
                asdict(before),
                indent=2,
                ensure_ascii=False,
            ))
            raise RuntimeError(
                "Trang thai ban dau chua dat; chua them Loopback."
            )

        backup_dir = PROJECT_DIR / ".local_backups"
        backup_dir.mkdir(mode=0o700, exist_ok=True)
        backup_dir.chmod(0o700)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_path = backup_dir / (
            f"R1_before_restore_{stamp}_{uuid4().hex[:8]}.cfg"
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
            "interface Loopback99\n"
            " description THU_KHOI_PHUC_PYTHON\n"
            " exit\n"
        )

        interfaces = device.send_command(
            "show ip interface brief"
        )

        if not has_loopback99(interfaces):
            raise RuntimeError(
                "Chua xac nhan duoc Loopback99 vua tao."
            )

        print("Da xac nhan Loopback99 ton tai.")
        print("Dang khoi phuc ban sao...")

        result = device.restore_config(baseline)
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # Mo phien SSH moi de kiem tra kha nang truy cap.
        device.disconnect()
        device.connect()
        print("Da ket noi lai R1 sau khoi phuc.")

        interfaces = device.send_command(
            "show ip interface brief"
        )

        if has_loopback99(interfaces):
            raise RuntimeError(
                "Khoi phuc chua dat: Loopback99 van ton tai."
            )

        print("PASS: Loopback99 da bien mat.")

        after = device.verify_config(baseline, checks)
        print(json.dumps(
            asdict(after),
            indent=2,
            ensure_ascii=False,
        ))

        if not after.passed:
            raise RuntimeError(
                "Kiem tra IP, trang thai cong hoac ping chua dat."
            )

        completed = True
        print("PASS: KHOI PHUC VA XAC MINH R1 THANH CONG.")
        print("Chua luu startup-config.")

    except Exception as error:
        print(f"THAT BAI: {type(error).__name__}: {error}")

        if change_started and not completed:
            print("Dung tai day, kiem tra console R1 truoc khi chay lai.")
            print("Ban sao truoc thu nghiem:", snapshot_path)

    finally:
        device.disconnect()
        print("Da dong ket noi.")


if __name__ == "__main__":
    main()
