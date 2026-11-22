import json
from dataclasses import asdict
from pathlib import Path

from app.devices.factory import DeviceFactory
from app.inventory import InventoryManager


PROJECT_DIR = Path(__file__).resolve().parent

LINKS = {
    "R1": ("10.10.12.1", "10.10.12.2"),
    "R2": ("10.10.12.2", "10.10.12.1"),
}


def verify_device(device_info):
    """Thử kỳ vọng đúng và kỳ vọng sai, không sửa thiết bị."""
    device = DeviceFactory.create(device_info)

    try:
        device.connect()
        local_ip, peer_ip = LINKS[device.name]

        config_text = (
            "interface FastEthernet1/0\n"
            f"ip address {local_ip} 255.255.255.252\n"
            "no shutdown\n"
        )

        checks = {
            "interfaces": {
                "FastEthernet1/0": {
                    "ip_address": local_ip,
                    "status": "up",
                    "protocol": "up",
                }
            },
            "ping": {
                "target": peer_ip,
                "source": local_ip,
                "min_success_percent": 100,
            },
        }

        result = device.verify_config(config_text, checks)
        print(f"\nKET QUA {device.name}")
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))

        wrong_checks = {
            "interfaces": {
                "FastEthernet1/0": {
                    "ip_address": "192.0.2.99",
                }
            }
        }
        wrong_result = device.verify_config(config_text, wrong_checks)

        assert not wrong_result.passed
        print("PASS: phat hien ky vong IP sai, khong sua thiet bi.")

        return result.passed

    finally:
        device.disconnect()


def main():
    """Xác minh đường thử nghiệm của R1 và R2."""
    manager = InventoryManager(
        PROJECT_DIR / "inventory" / "devices.yaml"
    )
    devices = [
        device
        for device in manager.load()
        if device.name in LINKS
    ]

    if {device.name for device in devices} != set(LINKS):
        print("LOI: inventory phai co du R1 va R2.")
        return

    passed_count = 0

    for device_info in devices:
        try:
            if verify_device(device_info):
                passed_count += 1
        except Exception as error:
            print(f"LOI {device_info.name}: {error}")

    print(f"\nXAC MINH DAT: {passed_count}/{len(devices)}")


if __name__ == "__main__":
    main()
