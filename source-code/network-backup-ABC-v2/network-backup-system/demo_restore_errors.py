import re
from pathlib import Path

from app.contracts import RestoreError
from app.inventory import InventoryManager
from app.devices.factory import DeviceFactory


PROJECT_DIR = Path(__file__).resolve().parent


def main():
    inventory = InventoryManager(
        PROJECT_DIR / "inventory" / "devices.yaml"
    )
    info = next(
        item for item in inventory.load()
        if item.name == "R1"
    )
    device = DeviceFactory.create(info)

    try:
        device.connect()
        baseline = device.backup_config()

        # Bo dong end cuoi cung khoi ban sao.
        lines = baseline.rstrip().splitlines()

        if lines[-1].strip() != "end":
            raise RuntimeError("Ban sao goc khong co dong end.")

        missing_end = "\n".join(lines[:-1]) + "\n"

        # Tao ban sao khac hostname, khong sua router.
        wrong_hostname, replacements = re.subn(
            r"^hostname\s+\S+[ \t]*$",
            "hostname WRONG_ROUTER",
            baseline,
            count=1,
            flags=re.MULTILINE,
        )

        if replacements != 1:
            raise RuntimeError("Khong tim thay hostname trong ban sao.")

        cases = [
            ("Cau hinh rong", ""),
            ("Chi co mot phan cau hinh", "interface Loopback99\n"),
            ("Ban sao thieu end", missing_end),
            ("Ban sao khac hostname", wrong_hostname),
        ]

        passed = 0

        for label, config_text in cases:
            try:
                device.restore_config(config_text)

            except RestoreError as error:
                passed += 1
                print(f"PASS: {label}")
                print(f"  Da tu choi: {error}")

            else:
                raise RuntimeError(
                    f"FAIL: '{label}' khong bi tu choi. "
                    "Dung kiem tra va xem console R1."
                )

        after = device.backup_config()

        if after != baseline:
            raise RuntimeError(
                "Running-config khac truoc kiem tra. "
                "Can doi chieu tren console R1."
            )

        print("PASS: running-config khong thay doi.")
        print(f"KIEM TRA TU CHOI BAN SAO LOI: {passed}/{len(cases)}")

    finally:
        device.disconnect()
        print("Da dong ket noi.")


if __name__ == "__main__":
    main()
