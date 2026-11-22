from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from app.contracts import InventoryError
from app.inventory import InventoryManager


PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_FILE = PROJECT_DIR / "inventory" / "devices.yaml"


def expect_error(action, message):
    """Xác nhận một thao tác sai bị từ chối."""
    try:
        action()
    except InventoryError as error:
        print(f"PASS {message}: {error}")
    else:
        raise AssertionError(f"FAIL {message}")


def main():
    """Kiểm tra CRUD trên bản sao tạm của inventory thật."""
    original = SOURCE_FILE.read_bytes()

    with TemporaryDirectory() as directory:
        test_file = Path(directory) / "devices.yaml"
        test_file.write_bytes(original)

        manager = InventoryManager(test_file)
        initial = manager.load()
        r1 = next(device for device in initial if device.name == "R1")

        test_name = "TEST_ROUTER"
        assert all(device.name != test_name for device in initial)

        test_device = replace(
            r1,
            name=test_name,
            host="192.0.2.10",
            group="test",
            tags=["temporary"],
        )

        manager.add(test_device)
        assert len(manager.load()) == len(initial) + 1
        print("PASS them thiet bi")

        before = test_file.read_bytes()
        expect_error(
            lambda: manager.add(test_device),
            "tu choi ten trung",
        )
        assert test_file.read_bytes() == before

        manager.update(test_name, {"host": "192.0.2.11"})
        selected = manager.filter(group="test", tag="temporary")
        assert len(selected) == 1
        assert selected[0].host == "192.0.2.11"
        print("PASS sua va loc thiet bi")

        before = test_file.read_bytes()
        expect_error(
            lambda: manager.update(test_name, {"port": 70000}),
            "tu choi port sai",
        )
        assert test_file.read_bytes() == before

        manager.delete(test_name)
        assert manager.load() == initial
        print("PASS xoa thiet bi")

        expect_error(
            lambda: manager.delete(test_name),
            "tu choi xoa thiet bi khong ton tai",
        )

    assert SOURCE_FILE.read_bytes() == original
    print("PASS inventory that giu nguyen")
    print("HOAN THANH KIEM TRA CRUD")


if __name__ == "__main__":
    main()
