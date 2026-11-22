import logging
import tempfile
import unittest
from pathlib import Path
from threading import TIMEOUT_MAX, Event, Thread
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.backup import BackupService
from app.contracts import BackupError, DeviceInfo
from app.scheduler import BackupScheduler, ScheduleEntry, load_schedule
from app.storage import BackupStorage


class FakeClock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now


def info(name):
    return DeviceInfo(name, "192.0.2.1", 22, "cisco_ios", "lab", "router", [], "LAB")


class FakeRunner:
    """Runner đồng bộ; chỉ runner cung cấp thiết bị cho task_callable."""

    def __init__(self):
        self.calls = []

    def run(self, device_infos, task_name, task_callable):
        self.calls.append((device_infos, task_name))
        return [task_callable(SimpleNamespace(name=d.name)) for d in device_infos]


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.runner = FakeRunner()
        self.service = Mock()
        self.service.create_backup.side_effect = lambda device: "backup-" + device.name
        self.logger = Mock(spec=logging.Logger)

    def scheduler(self, entries=None, **kwargs):
        scheduler = BackupScheduler(
            entries if entries is not None else [ScheduleEntry("R1", 10)],
            [info("R1"), info("R2")], self.runner, self.service,
            clock=self.clock, logger=self.logger, **kwargs,
        )
        self.addCleanup(scheduler.close)
        return scheduler

    def yaml_file(self, content):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "schedule.yaml"
        path.write_text(content, encoding="utf-8")
        return path

    def test_yaml_and_two_rounds_with_fake_clock(self):
        path = self.yaml_file("schedules:\n  - device: R1\n    interval_seconds: 10\n")
        scheduler = BackupScheduler.from_yaml(
            path, [info("R1")], self.runner, self.service, clock=self.clock,
        )
        self.addCleanup(scheduler.close)
        self.assertEqual(scheduler.run_pending(), {})
        for now in (10, 20):
            self.clock.now = now
            self.assertEqual(scheduler.run_pending()["R1"].result(timeout=2), ["backup-R1"])
            self.assertEqual(scheduler.run_pending(), {})
        self.assertEqual(self.runner.calls, [([info("R1")], "backup")] * 2)
        self.assertEqual(self.service.create_backup.call_count, 2)

    def test_invalid_yaml_is_rejected(self):
        invalid = [
            "", "[]", "schedules: []", "schedules: {}", "schedules: [R1]",
            "schedules: [{device: R1}]",
            "schedules: [{device: R1, interval_seconds: 10, typo: 1}]",
            "schedules: [{device: R1, interval_seconds: 10}]\nunknown: 1",
            "schedules: [{device: R1, device: R2, interval_seconds: 10}]",
            "schedules: [",
            "schedules: [{device: R1, interval_seconds: 10}, {device: R1, interval_seconds: 20}]",
        ]
        for value in ("0", "-1", "true", "null", "'10'", ".nan", ".inf"):
            invalid.append(f"schedules: [{{device: R1, interval_seconds: {value}}}]")
        invalid.append("schedules: [{device: R1, interval_seconds: " + "9" * 400 + "}]")
        for name in ("../R1", "null", "42"):
            invalid.append(f"schedules: [{{device: {name}, interval_seconds: 10}}]")
        for content in invalid:
            with self.subTest(content=content), self.assertRaises(BackupError):
                load_schedule(self.yaml_file(content))

    def test_missing_or_invalid_utf8_file(self):
        path = self.yaml_file("unused")
        path.write_bytes(b"\xff")
        with self.assertRaises(BackupError):
            load_schedule(path)
        path.unlink()
        with self.assertRaises(BackupError):
            load_schedule(path)

    def test_constructor_rejects_unknown_devices_and_invalid_options(self):
        for entries in ([ScheduleEntry("unknown", 10)], [ScheduleEntry("R1", True)],
                        [ScheduleEntry("R1", 0)], [],
                        [ScheduleEntry("R1", 10)] * 2):
            with self.subTest(entries=entries), self.assertRaises(BackupError):
                self.scheduler(entries)
        for workers in (0, -1, True, 1.5):
            with self.subTest(workers=workers), self.assertRaises(BackupError):
                self.scheduler(max_workers=workers)
        with self.assertRaises(BackupError):
            BackupScheduler([ScheduleEntry("R1", 10)], [info("R1")] * 2,
                            self.runner, self.service)

    def test_independent_intervals_and_no_catchup_burst(self):
        scheduler = self.scheduler([ScheduleEntry("R1", 10), ScheduleEntry("R2", 20)])
        self.clock.now = 10
        scheduler.run_pending()["R1"].result(timeout=2)
        self.clock.now = 100
        futures = scheduler.run_pending()
        self.assertEqual(set(futures), {"R1", "R2"})
        for future in futures.values():
            future.result(timeout=2)
        self.assertEqual(scheduler.run_pending(), {})
        self.assertEqual(len(self.runner.calls), 3)

    def test_running_device_does_not_overlap_or_block_other_device(self):
        entered, release = Event(), Event()

        def backup(device):
            if device.name == "R1":
                entered.set()
                if not release.wait(2):
                    raise RuntimeError("test release timeout")
            return device.name

        self.service.create_backup.side_effect = backup
        scheduler = self.scheduler([ScheduleEntry("R1", 10), ScheduleEntry("R2", 10)])
        self.addCleanup(release.set)
        self.clock.now = 10
        first = scheduler.run_pending()
        self.assertTrue(entered.wait(2))
        first["R2"].result(timeout=2)
        self.clock.now = 20
        second = scheduler.run_pending()
        self.assertEqual(set(second), {"R2"})
        second["R2"].result(timeout=2)
        self.logger.warning.assert_called()
        release.set()
        first["R1"].result(timeout=2)
        self.clock.now = 30
        for future in scheduler.run_pending().values():
            future.result(timeout=2)

    def test_queued_device_is_also_protected(self):
        entered, release = Event(), Event()

        def backup(device):
            entered.set()
            if not release.wait(2):
                raise RuntimeError("test release timeout")

        self.service.create_backup.side_effect = backup
        scheduler = self.scheduler([ScheduleEntry("R1", 10), ScheduleEntry("R2", 10)],
                                   max_workers=1)
        self.addCleanup(release.set)
        self.clock.now = 10
        futures = scheduler.run_pending()
        self.assertTrue(entered.wait(2))
        self.clock.now = 20
        self.assertEqual(scheduler.run_pending(), {})
        release.set()
        for future in futures.values():
            future.result(timeout=2)
        self.assertEqual(len(self.runner.calls), 2)

    def test_backup_failure_is_logged_and_next_round_recovers(self):
        scheduler = self.scheduler([ScheduleEntry("R1", 10), ScheduleEntry("R2", 10)])

        def backup(device):
            if device.name == "R1":
                raise BackupError("sensitive payload")
            return device.name

        self.service.create_backup.side_effect = backup
        self.clock.now = 10
        futures = scheduler.run_pending()
        with self.assertRaises(BackupError):
            futures["R1"].result(timeout=2)
        self.assertEqual(futures["R2"].result(timeout=2), ["R2"])
        self.assertNotIn("sensitive payload", str(self.logger.mock_calls))
        self.logger.error.assert_called()
        self.service.create_backup.side_effect = lambda device: device.name
        self.clock.now = 20
        self.assertEqual(scheduler.run_pending()["R1"].result(timeout=2), ["R1"])

    def test_failure_remains_logged_when_runner_catches_it(self):
        def run(infos, task_name, task):
            try:
                task(SimpleNamespace(name=infos[0].name))
            except BackupError:
                return {"failed": True}

        self.runner.run = run
        self.service.create_backup.side_effect = BackupError("secret")
        scheduler = self.scheduler()
        self.clock.now = 10
        self.assertEqual(scheduler.run_pending()["R1"].result(timeout=2), {"failed": True})
        self.logger.error.assert_called_once()
        self.assertNotIn("secret", str(self.logger.mock_calls))

    def test_two_rounds_save_real_versions_with_fake_connected_device(self):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(temp.cleanup)
        storage = BackupStorage(temp.name)
        service = BackupService(storage)
        device = SimpleNamespace(
            name="R1",
            get_normalized_facts=lambda: {"device_name": "R1", "platform": "cisco_ios"},
            backup_config=lambda: "hostname R1\r\n",
            create_restore_point=lambda: "opaque restore point\r\n",
        )
        self.runner.run = lambda infos, task_name, task: task(device)
        scheduler = BackupScheduler([ScheduleEntry("R1", 10)], [info("R1")],
                                    self.runner, service, clock=self.clock)
        self.addCleanup(scheduler.close)
        records = []
        for now in (10, 20):
            self.clock.now = now
            records.append(scheduler.run_pending()["R1"].result(timeout=2))
        self.assertNotEqual(records[0].backup_id, records[1].backup_id)
        self.assertEqual(len(service.list_backups("R1")), 2)
        for record in records:
            self.assertEqual(service.read_backup(record.backup_id), "hostname R1\r\n")
            self.assertEqual(storage.read_restore_point(record.backup_id),
                             "opaque restore point\r\n")

    def test_runner_connection_failure_does_not_stop_other_device(self):
        scheduler = self.scheduler([ScheduleEntry("R1", 10), ScheduleEntry("R2", 10)])
        original = self.runner.run

        def run(infos, name, task):
            if infos[0].name == "R1":
                raise ConnectionError("secret")
            return original(infos, name, task)

        self.runner.run = run
        self.clock.now = 10
        futures = scheduler.run_pending()
        with self.assertRaises(ConnectionError):
            futures["R1"].result(timeout=2)
        self.assertEqual(futures["R2"].result(timeout=2), ["backup-R2"])
        self.logger.error.assert_called()

    def test_submit_failure_does_not_stop_other_device(self):
        scheduler = self.scheduler([ScheduleEntry("R1", 10), ScheduleEntry("R2", 10)])
        original = scheduler._pool.submit
        self.clock.now = 10
        with patch.object(scheduler._pool, "submit", side_effect=[RuntimeError(),
                          original(lambda: "R2")]):
            futures = scheduler.run_pending()
        self.assertEqual(set(futures), {"R2"})
        self.assertEqual(futures["R2"].result(timeout=2), "R2")
        self.logger.error.assert_called()

    def test_stop_wakes_forever_and_closes_pool(self):
        scheduler = self.scheduler()
        loop_entered = Event()
        original = scheduler.run_pending

        def pending():
            loop_entered.set()
            return original()

        scheduler.run_pending = pending
        thread = Thread(target=scheduler.run_forever, kwargs={"poll_seconds": 60})
        thread.start()
        try:
            self.assertTrue(loop_entered.wait(2))
            scheduler.stop()
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertTrue(scheduler._closed)
            self.clock.now = 100
            self.assertEqual(scheduler.run_pending(), {})
        finally:
            scheduler.stop()
            thread.join(2)

    def test_close_waits_for_running_work_and_cancels_queue(self):
        entered, release, closing = Event(), Event(), Event()

        def backup(device):
            entered.set()
            if not release.wait(2):
                raise RuntimeError("test release timeout")

        self.service.create_backup.side_effect = backup
        scheduler = self.scheduler([ScheduleEntry("R1", 10), ScheduleEntry("R2", 10)],
                                   max_workers=1)
        self.addCleanup(release.set)
        self.clock.now = 10
        futures = scheduler.run_pending()
        self.assertTrue(entered.wait(2))

        def close():
            closing.set()
            scheduler.close()

        thread = Thread(target=close)
        thread.start()
        self.assertTrue(closing.wait(2))
        # shutdown marks the queued future cancelled before it waits for R1.
        cancelled = Event()
        futures["R2"].add_done_callback(lambda future: cancelled.set())
        try:
            self.assertTrue(cancelled.wait(2))
            self.assertTrue(thread.is_alive())
            self.assertTrue(futures["R2"].cancelled())
        finally:
            release.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(self.runner.calls), 1)

    def test_ctrl_c_closes_scheduler(self):
        scheduler = self.scheduler()
        with patch.object(scheduler, "run_pending", side_effect=KeyboardInterrupt):
            scheduler.run_forever()
        self.assertTrue(scheduler._closed)

    def test_invalid_poll_interval(self):
        scheduler = self.scheduler()
        for value in (0, -1, True, float("inf"), "1", TIMEOUT_MAX * 2):
            with self.subTest(value=value), self.assertRaises(BackupError):
                scheduler.run_forever(value)


if __name__ == "__main__":
    unittest.main()
