import base64
import json
from copy import deepcopy
from pathlib import Path

from app.contracts import RestoreError
from app.inventory import InventoryManager
from app.devices.factory import DeviceFactory


PROJECT_DIR = Path(__file__).resolve().parent


def config_commands(text):
    # Bo cac dong chu thich thoi gian cua export.
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


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

        point_text = device.create_restore_point()
        point = json.loads(point_text)
        before = device.backup_config()

        wrong_device = deepcopy(point)
        wrong_device["device_name"] = "OTHER_ROUTER"

        wrong_version = deepcopy(point)
        wrong_version["routeros_version"] = "WRONG_VERSION"

        corrupted = deepcopy(point)
        data = bytearray(base64.b64decode(point["binary_base64"]))
        data[0] ^= 1
        corrupted["binary_base64"] = base64.b64encode(data).decode("ascii")
        # Giu nguyen SHA256 de thu phat hien noi dung bi thay doi.

        cases = [
            ("Goi rong", ""),
            ("Dung nham ban export", before),
            ("Ban sao khac thiet bi", json.dumps(wrong_device)),
            ("Du lieu binary bi thay doi", json.dumps(corrupted)),
            ("Ban sao khac phien ban", json.dumps(wrong_version)),
        ]

        passed = 0

        for label, payload in cases:
            try:
                device.restore_config(payload)

            except RestoreError as error:
                passed += 1
                print(f"PASS: {label}")
                print(f"  Da tu choi: {error}")

            else:
                raise RuntimeError(
                    f"FAIL: '{label}' khong bi tu choi. "
                    "Dung va kiem tra console MT1."
                )

        after = device.backup_config()

        if config_commands(before) != config_commands(after):
            raise RuntimeError(
                "Cac lenh cau hinh khac truoc kiem tra. "
                "Can doi chieu tren MT1."
            )

        print("PASS: Cac lenh cau hinh khong thay doi.")
        print(f"TU CHOI GOI PHUC HOI LOI: {passed}/{len(cases)}")

    finally:
        device.disconnect()
        print("Da dong ket noi.")


if __name__ == "__main__":
    main()
