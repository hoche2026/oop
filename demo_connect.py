from getpass import getpass
from pathlib import Path

import yaml
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)


PROJECT_DIR = Path(__file__).resolve().parent
INVENTORY_FILE = PROJECT_DIR / "inventory" / "devices.yaml"


def load_device(name):
    """Đọc một thiết bị theo tên từ inventory."""
    with INVENTORY_FILE.open(encoding="utf-8") as file:
        inventory = yaml.safe_load(file)

    if not isinstance(inventory, dict):
        raise ValueError("Inventory phai la mot dictionary.")

    devices = inventory.get("devices")
    if not isinstance(devices, list):
        raise ValueError("Inventory phai co danh sach devices.")

    required_fields = (
        "name", "host", "port", "platform",
        "group", "role", "tags", "credential_profile",
    )
    names = set()

    for device in devices:
        if not isinstance(device, dict):
            raise ValueError("Moi thiet bi phai la mot dictionary.")

        for field in required_fields:
            if field not in device:
                raise ValueError(f"Thiet bi thieu truong: {field}")

        device_name = device["name"]
        if not isinstance(device_name, str) or not device_name.strip():
            raise ValueError("Ten thiet bi phai la chuoi khong rong.")

        if device_name in names:
            raise ValueError(f"Trung ten thiet bi: {device_name}")
        names.add(device_name)

    for device in devices:
        if device["name"] == name:
            return device

    raise ValueError(f"Khong tim thay thiet bi: {name}")


def main():
    """Đọc inventory, kết nối R1 và xem trạng thái cổng."""
    try:
        device = load_device("R1")

        print(f"Thiet bi: {device['name']}")
        print(f"IP: {device['host']} | Nen tang: {device['platform']}")

        password = getpass("Mat khau SSH: ")
        secret = getpass("Mat khau enable: ")

        connection_info = {
            "device_type": device["platform"],
            "host": device["host"],
            "port": device["port"],
            "username": "netadmin",
            "password": password,
            "secret": secret,
            "conn_timeout": 15,
            "auth_timeout": 30,
            "banner_timeout": 30,
            "ssh_strict": True,
            "system_host_keys": True,
        }

        print(f"Dang ket noi {device['name']}...")

        with ConnectHandler(**connection_info) as connection:
            connection.enable()
            print("Ket noi thanh cong:", connection.find_prompt())

            output = connection.send_command(
                "show ip interface brief",
                read_timeout=30,
            )
            print(output)

        print("Da dong ket noi SSH.")

    except FileNotFoundError:
        print(f"Khong tim thay file: {INVENTORY_FILE}")

    except yaml.YAMLError as error:
        print(f"Loi cu phap YAML: {error}")

    except ValueError as error:
        print(f"Loi du lieu hoac cau hinh: {error}")

    except NetmikoAuthenticationException:
        print("Loi xac thuc: kiem tra tai khoan va mat khau SSH.")

    except NetmikoTimeoutException as error:
        print(f"Loi ket noi SSH: {error}")

    except Exception as error:
        print(f"Loi {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()
