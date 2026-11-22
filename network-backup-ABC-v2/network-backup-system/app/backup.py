"""Nghiệp vụ phần B; thiết bị do A cung cấp, kết nối do C quản lý."""

from dataclasses import asdict
from difflib import unified_diff

from app.comparison import comparison_lines
from app.verification import required_criteria

from app.contracts import BackupError, RestoreError, VerificationError, VerificationResult
from app.storage import BackupStorage


class BackupService:
    """Quản lý vòng đời bản sao; nhận thiết bị đã được runner kết nối."""

    def __init__(self, storage=None):
        self.storage = storage if storage is not None else BackupStorage()

    @staticmethod
    def _identity(device):
        # A chưa có property platform công khai. Dùng API facts thay vì _info.
        name = device.name
        facts = device.get_normalized_facts()
        if not isinstance(facts, dict) or facts.get("device_name") != name:
            raise BackupError("Facts khong khop ten thiet bi.")
        platform = facts.get("platform")
        if not isinstance(platform, str) or not platform.strip():
            raise BackupError("Facts thieu platform hop le.")
        return name, platform

    def _save_device(self, device, name, platform):
        config_text = device.backup_config()
        point_text = device.create_restore_point()
        return self.storage.save_backup(name, platform, config_text, point_text)

    def create_backup(self, device):
        """Nhận thiết bị đã kết nối; lưu cả văn bản và gói phục hồi nguyên bản."""
        try:
            name, platform = self._identity(device)
            return self._save_device(device, name, platform)
        except BackupError:
            raise
        except Exception as exc:
            # Không đưa phản hồi SSH hoặc bí mật vào thông báo nghiệp vụ.
            raise BackupError(
                "Khong thu thap duoc ban sao tu thiet bi.") from exc

    def list_backups(self, device_name):
        """Liệt kê metadata các bản sao của một thiết bị, mới nhất trước."""
        return self.storage.list_backups(device_name)

    def read_backup(self, backup_id):
        """Đọc văn bản cấu hình và kiểm tra SHA256 trước khi trả dữ liệu."""
        return self.storage.read_backup(backup_id)

    @staticmethod
    def _comparison_lines(text):
        return comparison_lines(text)

    @classmethod
    def _diff(cls, first, second, first_label, second_label):
        return "".join(unified_diff(
            cls._comparison_lines(first), cls._comparison_lines(second),
            fromfile=first_label, tofile=second_label,
        ))

    def compare(self, first_id, second_id):
        """Trả unified diff giữa hai phiên bản cùng thiết bị và nền tảng."""
        first = self.storage.get_backup(first_id)
        second = self.storage.get_backup(second_id)
        if (first.device_name, first.platform) != (second.device_name, second.platform):
            raise BackupError(
                "Chi so sanh cac phien ban cung thiet bi va platform.")
        return self._diff(
            self.read_backup(first_id), self.read_backup(second_id),
            f"backup:{first_id}", f"backup:{second_id}",
        )

    def set_baseline(self, device_name, backup_id):
        """Chọn bản sao đúng chủ sở hữu và còn toàn vẹn làm cấu hình chuẩn."""
        self.storage.set_baseline(device_name, backup_id)

    def check_changes(self, device):
        """So cấu hình hiện tại với baseline và trả trạng thái cùng diff."""
        try:
            baseline = self.storage.get_baseline(device.name)
            name, platform = self._identity(device)
            if baseline.platform != platform:
                raise BackupError("Baseline khong khop platform cua thiet bi.")
            original = self.read_backup(baseline.backup_id)
            current = device.backup_config()
            if not isinstance(current, str) or not current.strip():
                raise BackupError("Thiet bi khong tra ve cau hinh hop le.")
            diff = self._diff(
                original, current, f"baseline:{baseline.backup_id}", f"current:{name}")
            return {
                "device": name,
                "baseline_id": baseline.backup_id,
                "changed": bool(diff),
                "diff": diff,
            }
        except BackupError:
            raise
        except Exception as exc:
            raise BackupError(
                "Khong kiem tra duoc thay doi cau hinh.") from exc

    def restore(self, device, backup_id, checks):
        """Sao lưu trước khi phục hồi, xác minh sau; không tự rollback lặp.

        Lỗi có thuộc tính pre_backup_id (None nếu chưa tạo bản sao) và stage
        để C ghi nhận được bản sao cứu hộ ngay cả khi restore/verify thất bại.
        """
        pre_backup_id = None
        stage = "validate"
        try:
            if not isinstance(checks, dict) or not checks:
                raise RestoreError(
                    "Can checks khong rong de xac minh khoi phuc.")
            record = self.storage.get_backup(backup_id)
            if record.device_name != device.name:
                raise RestoreError("Ban sao khong thuoc thiet bi duoc chon.")
            name, platform = self._identity(device)
            if record.platform != platform:
                raise RestoreError("Ban sao khong khop platform cua thiet bi.")
            config_text = self.read_backup(backup_id)
            point_text = self.storage.read_restore_point(backup_id)

            # A.validate checks qua chính verify_config trước mọi thay đổi.
            # passed=False ở trạng thái hiện tại là bình thường: đó có thể là
            # lý do cần restore. Ngoại lệ kiểm tra/cấu trúc thì dừng ngay.
            stage = "precheck"
            precheck = device.verify_config(config_text, checks)
            self._validate_verification(precheck, checks)

            stage = "pre_backup"
            pre_backup_id = self._save_device(device, name, platform).backup_id
            stage = "restore"
            restore_result = device.restore_config(point_text)
            if not isinstance(restore_result, dict):
                raise RestoreError(
                    "Ket qua khoi phuc cua thiet bi khong hop le.")
            stage = "verify"
            verification = device.verify_config(config_text, checks)
            self._validate_verification(verification, checks)
            if not verification.passed:
                error = VerificationError("Xac minh sau khoi phuc khong dat.")
                error.verification = asdict(verification)
                raise error
            return {
                "device": name,
                "backup_id": backup_id,
                "pre_backup_id": pre_backup_id,
                "restored": True,
                "verification": asdict(verification),
                "restore_result": restore_result,
            }
        except Exception as exc:
            if isinstance(exc, (RestoreError, VerificationError)):
                error = exc
            else:
                error = RestoreError(f"Khoi phuc that bai tai buoc {stage}.")
            error.pre_backup_id = pre_backup_id
            error.backup_id = backup_id
            error.stage = stage
            if error is exc:
                raise
            raise error from exc

    @staticmethod
    def _validate_verification(result, requested_checks):
        if (
            not isinstance(result, VerificationResult)
            or type(result.passed) is not bool
            or not isinstance(result.checks, dict)
            or not result.checks
            or any(type(value) is not bool for value in result.checks.values())
            or not isinstance(result.details, list)
            or not all(isinstance(detail, str) for detail in result.details)
            or result.passed != all(result.checks.values())
        ):
            raise VerificationError(
                "Ket qua xac minh thieu hoac khong nhat quan.")

        # Ánh xạ theo verify_config hiện có của A, không theo platform.
        interface_keys = {
            f"{name}.{field}"
            for name, expected in requested_checks.get("interfaces", {}).items()
            for field in expected
        }
        required = required_criteria(requested_checks)
        # A dùng cờ lỗi này khi không thu thập được interface. Đây là một
        # lần kiểm tra thất bại rõ ràng, được phép ở precheck; sau restore
        # passed=False vẫn bị từ chối. Cờ True không thay được tiêu chí thiếu.
        if result.checks.get("interfaces_collection") is False:
            required.difference_update(interface_keys)
        if not required.issubset(result.checks):
            error = VerificationError(
                "Ket qua xac minh thieu tieu chi duoc yeu cau.")
            error.verification = asdict(result)
            raise error
