from getpass import getpass
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from netmiko import ConnectHandler, file_transfer


def main():
    password = getpass("Mat khau SSH: ")
    secret = getpass("Mat khau enable: ")
    connection = None
    remote_name = f"oop_transfer_test_{uuid4().hex[:8]}.txt"

    try:
        print("Dang ket noi R1...")

        connection = ConnectHandler(
            device_type="cisco_ios",
            host="192.168.241.21",
            username="netadmin",
            password=password,
            secret=secret,
            conn_timeout=15,
            auth_timeout=30,
            banner_timeout=30,
            ssh_strict=True,
            system_host_keys=True,
        )
        connection.enable()

        with TemporaryDirectory() as temporary_dir:
            local_file = Path(temporary_dir) / remote_name
            local_file.write_text(
                "OOP SCP transfer test\n",
                encoding="utf-8",
            )

            print("Dang chuyen file thu len disk0:...")

            result = file_transfer(
                connection,
                source_file=str(local_file),
                dest_file=remote_name,
                file_system="disk0:",
                direction="put",
                overwrite_file=False,
                disable_md5=False,
            )

        print("Ket qua:", result)

        if not result.get("file_verified"):
            raise RuntimeError("Chua xac minh duoc noi dung file.")

        print("THANH CONG: file da duoc chuyen va xac minh.")
        print("File tren R1:", f"disk0:{remote_name}")
        print("Chua thuc hien khoi phuc cau hinh.")

    except Exception as error:
        print(f"THAT BAI: {type(error).__name__}: {error}")

    finally:
        if connection is not None:
            connection.disconnect()
            print("Da dong ket noi.")


if __name__ == "__main__":
    main()
