from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceInfo:
    """Thông tin thiết bị, không chứa mật khẩu."""

    name: str
    host: str
    port: int
    platform: str
    group: str
    role: str
    tags: list[str]
    credential_profile: str


class InventoryError(Exception):
    """Lỗi dữ liệu hoặc thao tác inventory."""


class DeviceConnectionError(Exception):
    """Lỗi kết nối thiết bị."""


class DeviceCommandError(Exception):
    """Lỗi thực thi lệnh thiết bị."""


class BackupError(Exception):
    """Lỗi sao lưu cấu hình."""


class RestoreError(Exception):
    """Lỗi khôi phục cấu hình."""


class VerificationError(Exception):
    """Lỗi xác minh kết quả."""


@dataclass
class VerificationResult:
    """Kết quả xác minh các điều kiện được yêu cầu."""

    passed: bool
    details: list[str]
    checks: dict[str, bool]
