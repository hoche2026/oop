import base64
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

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
        point_text = device.create_restore_point()
        point = json.loads(point_text)

        data = base64.b64decode(
            point["binary_base64"],
            validate=True,
        )

        if len(data) != point["size_bytes"]:
            raise RuntimeError("Dung luong khong khop.")

        if hashlib.sha256(data).hexdigest() != point["sha256"]:
            raise RuntimeError("SHA256 khong khop.")

        folder = PROJECT_DIR / ".local_backups"
        folder.mkdir(mode=0o700, exist_ok=True)
        folder.chmod(0o700)

        path = folder / (
            f"MT1_{uuid4().hex}.restorepoint.json"
        )
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )

        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(point_text)

        print("Thiet bi:", point["device_name"])
        print("Hostname:", point["hostname"])
        print("RouterOS:", point["routeros_version"])
        print("Dung luong binary:", point["size_bytes"], "bytes")
        print("Da luu:", path)
        print("PASS: TAO VA TAI BAN SAO PHUC HOI MIKROTIK.")
        print("Chua thuc hien khoi phuc.")

    finally:
        device.disconnect()
        print("Da dong ket noi.")


if __name__ == "__main__":
    main()
