import os
import re
import tempfile
from dataclasses import asdict
from ipaddress import ip_address
from pathlib import Path

import yaml

from app.contracts import DeviceInfo, InventoryError


class InventoryManager:
    """Đọc, lọc, thêm, sửa và xóa thiết bị trong file YAML."""

    def __init__(self, file_path):
        self._file_path = Path(file_path)

    @staticmethod
    def _parse_device(record):
        """Kiểm tra bản ghi và chuyển thành DeviceInfo."""
        if not isinstance(record, dict):
            raise InventoryError("Moi thiet bi phai la dictionary.")

        required_fields = (
            "name", "host", "port", "platform",
            "group", "role", "tags", "credential_profile",
        )

        missing = [field for field in required_fields if field not in record]
        if missing:
            raise InventoryError(f"Thieu truong: {', '.join(missing)}")

        unknown = set(record) - set(required_fields)
        if unknown:
            raise InventoryError(f"Truong khong ho tro: {', '.join(unknown)}")

        string_fields = (
            "name", "host", "platform",
            "group", "role", "credential_profile",
        )
        for field in string_fields:
            value = record[field]
            if not isinstance(value, str) or not value.strip():
                raise InventoryError(f"{field} phai la chuoi khong rong.")

        if not re.fullmatch(r"[A-Za-z0-9_-]+", record["name"]):
            raise InventoryError("Ten chi duoc chua chu, so, _ va -.")

        try:
            ip_address(record["host"])
        except ValueError as error:
            raise InventoryError(
                f"IP khong hop le: {record['host']}"
            ) from error

        port = record["port"]
        if type(port) is not int or not 1 <= port <= 65535:
            raise InventoryError("port phai la so nguyen tu 1 den 65535.")

        tags = record["tags"]
        if not isinstance(tags, list) or not all(
            isinstance(tag, str) and tag.strip() for tag in tags
        ):
            raise InventoryError(
                "tags phai la danh sach cac chuoi khong rong.")

        return DeviceInfo(**{
            **record,
            "tags": list(tags),
        })

    @classmethod
    def _validate_records(cls, records):
        """Kiểm tra danh sách thiết bị và tên trùng."""
        if not isinstance(records, list):
            raise InventoryError("devices phai la danh sach.")

        devices = []
        names = set()

        for record in records:
            device = cls._parse_device(record)
            if device.name in names:
                raise InventoryError(f"Trung ten thiet bi: {device.name}")

            names.add(device.name)
            devices.append(device)

        return devices

    def load(self):
        """Đọc và kiểm tra toàn bộ inventory."""
        try:
            with self._file_path.open(encoding="utf-8") as file:
                inventory = yaml.safe_load(file)
        except (OSError, yaml.YAMLError) as error:
            raise InventoryError(
                f"Khong doc duoc inventory: {error}") from error

        if not isinstance(inventory, dict):
            raise InventoryError("Inventory phai la dictionary.")

        return self._validate_records(inventory.get("devices"))

    def filter(self, group=None, role=None, tag=None):
        """Lọc theo tất cả điều kiện được cung cấp."""
        return [
            device
            for device in self.load()
            if (group is None or device.group == group)
            and (role is None or device.role == role)
            and (tag is None or tag in device.tags)
        ]

    def _save(self, devices):
        """Kiểm tra dữ liệu rồi ghi qua file tạm để tránh file ghi dở."""
        records = [asdict(device) for device in devices]
        self._validate_records(records)
        temporary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._file_path.parent,
                prefix=".inventory-",
                suffix=".yaml",
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                yaml.safe_dump(
                    {"devices": records},
                    file,
                    allow_unicode=True,
                    sort_keys=False,
                )

            os.replace(temporary_path, self._file_path)

        except (OSError, yaml.YAMLError) as error:
            raise InventoryError(
                f"Khong luu duoc inventory: {error}") from error

        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def add(self, device_info):
        """Thêm một DeviceInfo, từ chối dữ liệu sai hoặc tên trùng."""
        if not isinstance(device_info, DeviceInfo):
            raise InventoryError("add() yeu cau doi tuong DeviceInfo.")

        devices = self.load()
        devices.append(device_info)
        self._save(devices)

    def update(self, name, changes):
        """Sửa các trường của một thiết bị theo tên hiện tại."""
        if not isinstance(changes, dict) or not changes:
            raise InventoryError("changes phai la dictionary khong rong.")

        devices = self.load()

        for index, device in enumerate(devices):
            if device.name == name:
                record = asdict(device)
                record.update(changes)
                devices[index] = self._parse_device(record)
                self._save(devices)
                return

        raise InventoryError(f"Khong tim thay thiet bi: {name}")

    def delete(self, name):
        """Xóa thiết bị theo tên, báo lỗi nếu không tồn tại."""
        devices = self.load()
        remaining = [device for device in devices if device.name != name]

        if len(remaining) == len(devices):
            raise InventoryError(f"Khong tim thay thiet bi: {name}")

        self._save(remaining)
