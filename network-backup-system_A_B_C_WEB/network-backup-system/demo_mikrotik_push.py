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
    attempted = False

    count_command = (
        ':put [:len [/interface bridge find '
        'where name="oop-test"]]'
    )

    try:
        device.connect()

        existing = int(device.send_command(count_command).strip())

        if existing != 0:
            raise RuntimeError(
                "Bridge oop-test da ton tai. Dung de tranh "
                "tac dong len cau hinh co san."
            )

        attempted = True
        result = device.push_config(
            '/interface bridge add name="oop-test" '
            'protocol-mode=none comment="THU_PUSH_PYTHON"'
        )
        print("So lenh da ap:", result["commands_sent"])

        count = int(device.send_command(count_command).strip())

        if count != 1:
            raise RuntimeError("Chua xac nhan bridge vua tao.")

        comment = device.send_command(
            ':put [/interface bridge get '
            '[find where name="oop-test"] comment]'
        ).strip()

        if comment != "THU_PUSH_PYTHON":
            raise RuntimeError("Comment bridge khong dung.")

        print("PASS: Tao bridge va doc lai comment dung.")

    finally:
        try:
            if attempted:
                device.push_config(
                    '/interface bridge remove '
                    '[find where name="oop-test"]'
                )

                remaining = int(
                    device.send_command(count_command).strip()
                )

                if remaining != 0:
                    raise RuntimeError("Chua xoa duoc bridge thu.")

                print("PASS: Da xoa bridge thu nghiem.")

        finally:
            device.disconnect()
            print("Da dong ket noi.")

    print("PASS: PUSH CONFIG MIKROTIK THANH CONG.")


if __name__ == "__main__":
    main()
