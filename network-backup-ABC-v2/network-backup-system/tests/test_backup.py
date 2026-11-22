import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.backup import BackupService
from app.contracts import (
    BackupError, DeviceCommandError, DeviceInfo, RestoreError,
    VerificationError, VerificationResult,
)
from app.devices.cisco_ios import CiscoIOSDevice
from app.storage import BackupStorage


class FakeDevice:
    """Thiết bị offline có restore point tách biệt văn bản cấu hình."""

    def __init__(self, name="R1", platform="cisco_ios"):
        self.name = name
        self.platform = platform
        self.config = f"hostname {name}\n"
        self.points = {}
        self.calls = []
        self.verify_passed = True

    def get_normalized_facts(self):
        self.calls.append("facts")
        return {"device_name": self.name, "platform": self.platform}

    def backup_config(self):
        self.calls.append("backup")
        return self.config

    def create_restore_point(self):
        self.calls.append("point")
        point = json.dumps({"opaque_restore_token": len(self.points)})
        self.points[point] = self.config
        return point

    def restore_config(self, point):
        self.calls.append("restore")
        self.config = self.points[point]
        # Mô phỏng kết quả A không có khóa restored chung.
        return {"reconnected": True, "post_checks_required": True}

    def verify_config(self, config_text, checks):
        self.calls.append("verify")
        results = {
            f"{name}.{field}": self.verify_passed
            for name, expected in checks.get("interfaces", {}).items()
            for field in expected
        }
        if checks.get("ping") is not None:
            results["ping"] = self.verify_passed
        return VerificationResult(self.verify_passed, [], results)

    def connect(self):
        raise AssertionError("B khong quan ly ket noi")

    def disconnect(self):
        raise AssertionError("B khong dong ket noi")


class BackupServiceTests(unittest.TestCase):
    CHECKS = {"ping": {
        "target": "192.0.2.1", "source": "192.0.2.2", "min_success_percent": 100,
    }}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix="backup_test_", dir=Path(__file__).resolve().parents[1]
        )
        self.addCleanup(self.temp.cleanup)
        self.storage = BackupStorage(self.temp.name)
        self.service = BackupService(self.storage)
        self.device = FakeDevice()

    def save(self):
        return self.service.create_backup(self.device)

    def test_create_list_read_and_opaque_restore_point(self):
        for platform in ("cisco_ios", "mikrotik_routeros"):
            with self.subTest(platform=platform):
                self.device.platform = platform
                record = self.save()
                self.assertEqual(record.platform, platform)
                self.assertEqual(self.service.read_backup(
                    record.backup_id), self.device.config)
                point = self.storage.read_restore_point(record.backup_id)
                self.assertIn(point, self.device.points)
                self.assertNotEqual(point, self.device.config)
                self.assertEqual(self.service.list_backups("R1")[0], record)

    def test_diff_detects_addition_removal_and_identical_versions(self):
        first = self.save()
        self.device.config = "hostname R1\ninterface Loopback0\n"
        second = self.save()
        diff = self.service.compare(first.backup_id, second.backup_id)
        self.assertIn("+interface Loopback0", diff)
        self.assertIn("-interface Loopback0",
                      self.service.compare(second.backup_id, first.backup_id))
        self.assertEqual(self.service.compare(
            first.backup_id, first.backup_id), "")

    def test_comparison_ignores_line_endings_but_preserves_comments(self):
        self.device.config = "hostname R1\r\n"
        first = self.save()
        self.device.config = "hostname R1"
        second = self.save()
        self.assertEqual(self.service.compare(
            first.backup_id, second.backup_id), "")
        self.assertEqual(self.service.read_backup(
            first.backup_id), "hostname R1\r\n")
        self.device.config = "hostname R1\n! timestamp changed\n"
        third = self.save()
        self.assertIn("+! timestamp changed",
                      self.service.compare(first.backup_id, third.backup_id))

    def test_baseline_drift_does_not_create_extra_restore_point(self):
        record = self.save()
        self.service.set_baseline("R1", record.backup_id)
        result = self.service.check_changes(self.device)
        self.assertFalse(result["changed"])
        self.assertEqual(result["diff"], "")
        self.device.config += "interface Loopback0\n"
        result = self.service.check_changes(self.device)
        self.assertEqual(result["baseline_id"], record.backup_id)
        self.assertTrue(result["changed"])
        self.assertIn("+interface Loopback0", result["diff"])
        self.assertEqual(len(self.device.points), 1)

    def test_missing_baseline_does_not_report_unchanged(self):
        with self.assertRaises(BackupError):
            self.service.check_changes(self.device)

    def test_platform_mismatch_is_rejected_by_drift_and_compare(self):
        first = self.save()
        self.service.set_baseline("R1", first.backup_id)
        self.device.platform = "mikrotik_routeros"
        second = self.save()
        with self.assertRaises(BackupError):
            self.service.check_changes(self.device)
        with self.assertRaises(BackupError):
            self.service.compare(first.backup_id, second.backup_id)

    def test_collection_failure_does_not_publish_backup(self):
        with patch.object(self.device, "create_restore_point", side_effect=RuntimeError("SSH failure")):
            with self.assertRaises(BackupError):
                self.save()
        self.assertEqual(self.service.list_backups("R1"), [])

    def test_invalid_facts_or_empty_current_configuration_are_rejected(self):
        with patch.object(self.device, "get_normalized_facts", return_value={"device_name": "other"}):
            with self.assertRaises(BackupError):
                self.save()
        record = self.save()
        self.service.set_baseline("R1", record.backup_id)
        self.device.config = ""
        with self.assertRaises(BackupError):
            self.service.check_changes(self.device)

    def test_restore_preserves_before_state_and_calls_a_in_order(self):
        record = self.save()
        self.device.config += "interface Loopback0\n"
        before = self.device.config
        self.device.calls.clear()
        result = self.service.restore(
            self.device, record.backup_id, self.CHECKS)
        self.assertTrue(result["restored"])
        self.assertEqual(self.device.config, "hostname R1\n")
        self.assertEqual(self.service.read_backup(
            result["pre_backup_id"]), before)
        self.assertTrue(result["verification"]["passed"])
        self.assertEqual(self.device.calls, [
                         "facts", "verify", "backup", "point", "restore", "verify"])
        json.dumps(result)  # C có thể xuất kết quả JSON.

    def test_restore_wrong_device_or_platform_never_changes_device(self):
        record = self.save()
        for device in (FakeDevice("R2"), FakeDevice(platform="other")):
            with self.subTest(device=device.name, platform=device.platform):
                with self.assertRaises(RestoreError) as caught:
                    self.service.restore(device, record.backup_id, self.CHECKS)
                self.assertIsNone(caught.exception.pre_backup_id)
                self.assertNotIn("restore", device.calls)
                self.assertEqual(len(self.service.list_backups("R1")), 1)

    def test_corrupt_target_is_rejected_before_pre_backup(self):
        record = self.save()
        point = next((Path(self.temp.name) / "backups/R1").glob("*.restore"))
        point.write_bytes(b"tampered")
        self.device.calls.clear()
        with self.assertRaises(RestoreError):
            self.service.restore(self.device, record.backup_id, self.CHECKS)
        self.assertNotIn("point", self.device.calls)
        self.assertNotIn("restore", self.device.calls)

    def test_empty_or_unsupported_checks_stop_before_changes(self):
        record = self.save()
        with self.assertRaises(RestoreError):
            self.service.restore(self.device, record.backup_id, {})
        with patch.object(self.device, "verify_config", side_effect=VerificationError("unsupported")):
            with self.assertRaises(VerificationError) as caught:
                self.service.restore(
                    self.device, record.backup_id, {"unknown": True})
        self.assertEqual(caught.exception.stage, "precheck")
        self.assertNotIn("restore", self.device.calls)

    def test_pre_backup_failure_prevents_restore(self):
        record = self.save()
        with patch.object(self.storage, "save_backup", side_effect=BackupError("disk failure")):
            with self.assertRaises(RestoreError) as caught:
                self.service.restore(
                    self.device, record.backup_id, self.CHECKS)
        self.assertEqual(caught.exception.stage, "pre_backup")
        self.assertIsNone(caught.exception.pre_backup_id)
        self.assertNotIn("restore", self.device.calls)

    def test_restore_failure_keeps_rescue_id_and_does_not_retry(self):
        record = self.save()
        with patch.object(self.device, "restore_config", side_effect=RuntimeError("timeout")) as restore:
            with self.assertRaises(RestoreError) as caught:
                self.service.restore(
                    self.device, record.backup_id, self.CHECKS)
            self.assertEqual(restore.call_count, 1)
        self.assertEqual(caught.exception.stage, "restore")
        self.assertIsNotNone(caught.exception.pre_backup_id)
        self.assertEqual(self.service.read_backup(
            caught.exception.pre_backup_id), "hostname R1\n")

    def test_failed_verification_never_reports_restore_success(self):
        record = self.save()
        self.device.verify_passed = False
        with self.assertRaises(VerificationError) as caught:
            self.service.restore(self.device, record.backup_id, self.CHECKS)
        self.assertEqual(caught.exception.stage, "verify")
        self.assertIsNotNone(caught.exception.pre_backup_id)
        self.assertFalse(caught.exception.verification["passed"])
        self.assertEqual(self.device.calls.count("restore"), 1)

    def test_empty_or_inconsistent_verification_is_not_success(self):
        record = self.save()
        for verification in (
            VerificationResult(True, [], {}),
            VerificationResult(True, [], {"ping": False}),
            {"passed": True},
        ):
            with self.subTest(result=verification):
                with patch.object(self.device, "verify_config", return_value=verification):
                    with self.assertRaises(VerificationError):
                        self.service.restore(
                            self.device, record.backup_id, self.CHECKS)
        self.assertNotIn("restore", self.device.calls)

    def test_missing_criteria_block_precheck_and_post_restore(self):
        checks = {
            **self.CHECKS,
            "interfaces": {
                "Loopback0": {"status": "up", "protocol": "up"},
                "Loopback1": {"status": "up"},
            },
        }
        complete = {"ping": True, "Loopback0.status": True,
                    "Loopback0.protocol": True, "Loopback1.status": True}
        record = self.save()
        # Thiếu ping, một trường, hoặc cả interface; cả hai giai đoạn đều
        # phải từ chối dù passed=True và các tiêu chí đã trả đều True.
        for missing in ({"ping"}, {"Loopback0.protocol"}, {"Loopback1.status"},
                        {"Loopback0.status", "Loopback0.protocol"}):
            for stage in ("precheck", "verify"):
                with self.subTest(missing=missing, stage=stage):
                    self.device.calls.clear()
                    before = "hostname R1\ninterface Loopback99\n"
                    self.device.config = before
                    partial = VerificationResult(
                        True, [], {
                            key: value for key, value in complete.items() if key not in missing},
                    )
                    responses = [partial] if stage == "precheck" else [
                        VerificationResult(True, [], complete), partial,
                    ]
                    with patch.object(self.device, "verify_config", side_effect=responses):
                        with self.assertRaises(VerificationError) as caught:
                            self.service.restore(
                                self.device, record.backup_id, checks)
                    error = caught.exception
                    self.assertEqual(error.stage, stage)
                    self.assertEqual(
                        error.verification["checks"], partial.checks)
                    if stage == "precheck":
                        self.assertIsNone(error.pre_backup_id)
                        self.assertNotIn("restore", self.device.calls)
                    else:
                        self.assertEqual(self.device.calls.count("restore"), 1)
                        self.assertEqual(self.service.read_backup(
                            error.pre_backup_id), before)

    def cisco_with_fake_io(self):
        # Không đọc .env thật, không tạo phiên SSH. verify_config giữ nguyên;
        # chỉ thay các điểm I/O/thu thập bằng dữ liệu tổng hợp.
        with patch("app.devices.base.load_dotenv"), patch.dict(os.environ, {
            "OFFLINE_USERNAME": "test", "OFFLINE_PASSWORD": "test",
        }, clear=True):
            device = CiscoIOSDevice(DeviceInfo(
                "R1", "192.0.2.1", 22, "cisco_ios", "test", "router", [], "OFFLINE",
            ))
        for method in ("connect", "disconnect"):
            mock = patch.object(device, method, side_effect=AssertionError(
                "Unexpected SSH lifecycle"))
            mock.start()
            self.addCleanup(mock.stop)
        for method in ("get_normalized_facts", "backup_config", "create_restore_point", "restore_config"):
            mock = patch.object(
                device, method, side_effect=getattr(self.device, method))
            mock.start()
            self.addCleanup(mock.stop)
        return device

    def test_cisco_fixture_and_full_checks_use_real_a_verification(self):
        device = self.cisco_with_fake_io()
        record = self.service.create_backup(device)
        parsed = [{"interface": "Loopback0", "ip_address": "192.0.2.2",
                   "status": "up", "proto": "up"}]
        for checks in (self.CHECKS, {**self.CHECKS, "interfaces": {
            "Loopback0": {"ip_address": "192.0.2.2", "status": "up", "protocol": "up"},
        }}, {"interfaces": {"Loopback0": {"status": "up"}}}):
            with self.subTest(checks=checks), patch.object(
                device, "send_command", return_value="Success rate is 100 percent (5/5)",
            ) as send, patch.object(device, "_collect_parsed", return_value=parsed):
                result = self.service.restore(device, record.backup_id, checks)
                self.assertTrue(result["restored"])
                self.assertTrue(result["verification"]["passed"])
                if "ping" in checks:
                    self.assertEqual(send.call_count, 2)
                    send.assert_called_with(
                        "ping 192.0.2.1 source 192.0.2.2 repeat 5 timeout 2")
                else:
                    send.assert_not_called()

    def test_cisco_without_source_is_rejected_by_real_a_before_io(self):
        device = self.cisco_with_fake_io()
        record = self.service.create_backup(device)
        self.device.calls.clear()
        with patch.object(device, "send_command") as send:
            with self.assertRaises(VerificationError) as caught:
                self.service.restore(device, record.backup_id, {
                                     "ping": {"target": "192.0.2.1"}})
        self.assertEqual(caught.exception.stage, "precheck")
        self.assertIsNone(caught.exception.pre_backup_id)
        self.assertNotIn("restore", self.device.calls)
        send.assert_not_called()

    def test_real_a_collection_failure_allows_precheck_but_never_post_success(self):
        checks = {**self.CHECKS, "interfaces": {"Loopback0": {"status": "up"}}}
        device = self.cisco_with_fake_io()
        record = self.service.create_backup(device)
        parsed = [{"interface": "Loopback0", "status": "up"}]
        for responses, fails in (([DeviceCommandError("offline"), parsed], False),
                                 ([parsed, DeviceCommandError("offline")], True)):
            with self.subTest(fails=fails), patch.object(
                device, "send_command", return_value="Success rate is 100 percent (5/5)",
            ), patch.object(device, "_collect_parsed", side_effect=responses):
                if fails:
                    with self.assertRaises(VerificationError) as caught:
                        self.service.restore(device, record.backup_id, checks)
                    self.assertEqual(caught.exception.stage, "verify")
                    self.assertIsNotNone(caught.exception.pre_backup_id)
                    self.assertFalse(caught.exception.verification["passed"])
                else:
                    self.assertTrue(self.service.restore(
                        device, record.backup_id, checks)["restored"])

    def test_collection_success_flag_cannot_replace_missing_criteria(self):
        record = self.save()
        checks = {"interfaces": {"Loopback0": {"status": "up"}}}
        with patch.object(self.device, "verify_config", return_value=VerificationResult(
            True, [], {"interfaces_collection": True},
        )):
            with self.assertRaises(VerificationError) as caught:
                self.service.restore(self.device, record.backup_id, checks)
        self.assertEqual(caught.exception.stage, "precheck")
        self.assertIsNone(caught.exception.pre_backup_id)


if __name__ == "__main__":
    unittest.main()
