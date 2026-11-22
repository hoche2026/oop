import os
from abc import ABC, abstractmethod
from pathlib import Path

from dotenv import load_dotenv

from app.contracts import DeviceConnectionError, DeviceInfo


PROJECT_DIR = Path(__file__).resolve().parents[2]


class NetworkDevice(ABC):
    """Định nghĩa giao tiếp chung cho các thiết bị mạng."""

    def __init__(self, device_info):
        if not isinstance(device_info, DeviceInfo):
            raise TypeError("device_info phai la DeviceInfo.")

        self._info = device_info
        self._connection = None

        load_dotenv(PROJECT_DIR / ".env", override=False)
        profile = device_info.credential_profile

        self._username = os.getenv(f"{profile}_USERNAME")
        self._password = os.getenv(f"{profile}_PASSWORD")
        self._secret = os.getenv(f"{profile}_SECRET", "")

        if not self._username or not self._password:
            raise DeviceConnectionError(
                f"Thieu thong tin xac thuc cho profile {profile}."
            )

    @property
    def name(self):
        """Tên thiết bị."""
        return self._info.name

    @property
    def host(self):
        """Địa chỉ quản trị."""
        return self._info.host

    def _discard_connection(self):
        """Best-effort cleanup without masking the original failure."""
        try:
            self.disconnect()
        except Exception:
            self._connection = None

    def _reuse_connection(self):
        """Reuse only a live SSH connection; discard stale handles."""
        if self._connection is None:
            return False

        try:
            if self._connection.is_alive():
                return True
        except Exception:
            pass

        self._discard_connection()
        return False

    @abstractmethod
    def connect(self):
        """Mở kết nối."""

    @abstractmethod
    def disconnect(self):
        """Đóng kết nối."""

    @abstractmethod
    def send_command(self, command):
        """Gửi lệnh và trả về chuỗi kết quả."""

    @abstractmethod
    def backup_config(self):
        """Trả về nội dung cấu hình."""

    @abstractmethod
    def get_facts(self):
        """Thu thập thông tin và trả về dictionary chuẩn hóa."""

    @abstractmethod
    def push_config(self, config_text):
        """Áp cấu hình và trả về kết quả thực thi."""

    @abstractmethod
    def verify_config(self, config_text, checks):
        """Xác minh các điều kiện sau cấu hình."""
    @abstractmethod
    def restore_config(self, config_text: str):
        """Khoi phuc running-config tu ban sao luu."""
        pass
    def create_restore_point(self):
        """Mac dinh dung cau hinh van ban de khoi phuc."""
        return self.backup_config()
    def get_normalized_facts(self):
        from app.normalization import normalize_facts

        return normalize_facts(self.get_facts())
