from pathlib import Path

from rich.console import Console
from rich.table import Table

from app.inventory import InventoryManager
from app.devices.factory import DeviceFactory


PROJECT_DIR = Path(__file__).resolve().parent
console = Console()


def section_status(facts, *keys):
    for key in keys:
        section = facts.get(key)

        if isinstance(section, dict):
            return str(section.get("status", "unknown"))

    return "-"


def main():
    inventory = InventoryManager(
        PROJECT_DIR / "inventory" / "devices.yaml"
    )
    devices = inventory.load()

    required = {"R1", "R2", "SW1", "MT1"}
    found = {info.name for info in devices}
    missing = required - found

    if missing:
        raise RuntimeError(
            f"Inventory thieu thiet bi: {sorted(missing)}"
        )

    summary = Table(title="KET NOI VA THU THAP")
    summary.add_column("Thiet bi")
    summary.add_column("Lop")
    summary.add_column("So cong", justify="right")
    summary.add_column("Dong config/export", justify="right")
    summary.add_column("Ket qua")

    sections = Table(title="TRANG THAI DU LIEU")
    for heading in (
        "Thiet bi", "Route", "ARP", "Neighbor",
        "CPU", "RAM", "VLAN", "MAC",
    ):
        sections.add_column(heading)

    succeeded = 0

    for info in devices:
        device = None
        stage = "tao doi tuong"

        try:
            device = DeviceFactory.create(info)

            stage = "ket noi"
            console.print(f"Dang thu thap {info.name}...")
            device.connect()

            stage = "lay facts"
            facts = device.get_facts()

            stage = "lay cau hinh"
            config = device.backup_config()

            summary.add_row(
                info.name,
                type(device).__name__,
                str(len(facts.get("interfaces", []))),
                str(len(config.splitlines())),
                "ok",
            )

            sections.add_row(
                info.name,
                section_status(facts, "routing_table"),
                section_status(facts, "arp_table"),
                section_status(facts, "neighbors", "cdp_neighbors"),
                section_status(facts, "cpu"),
                section_status(facts, "memory"),
                section_status(facts, "vlans"),
                section_status(facts, "mac_table"),
            )

            succeeded += 1

        except Exception as error:
            class_name = (
                type(device).__name__
                if device is not None else "-"
            )

            summary.add_row(
                info.name,
                class_name,
                "-",
                "-",
                f"error: {stage}",
            )

            console.print(
                f"{info.name}: {type(error).__name__} "
                f"tai buoc {stage}"
            )

        finally:
            if device is not None:
                try:
                    device.disconnect()
                except Exception as error:
                    console.print(
                        f"{info.name}: loi dong ket noi "
                        f"({type(error).__name__})"
                    )

    console.print(summary)
    console.print(sections)
    console.print(
        f"\nKET NOI VA THU THAP: {succeeded}/{len(devices)}"
    )
    console.print(
        "Can xem bang status de danh gia chat luong tung muc."
    )

    return 0 if succeeded == len(devices) else 1


if __name__ == "__main__":
    raise SystemExit(main())
