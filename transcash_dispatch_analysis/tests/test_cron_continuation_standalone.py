"""Avoid scheduler poll gaps without changing invoice writes or transactions."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_import_queue_standalone import Job, Snapshot, module
from test_recovery_standalone import prepared


def queue(job, others=()):
    events = {"notifications": [], "wakeups": []}
    jobs = [job, *others]
    for item in jobs:
        item._schedule_import = lambda item=item: events["wakeups"].append(item.id)
    job.env.models["ir.cron"] = SimpleNamespace(_notify_progress=lambda **kw: events["notifications"].append(kw))
    runner = SimpleNamespace(env=job.env,
        search=lambda *a, **kw: [j for j in jobs if j.state in ("queued", "loading")],
        search_count=lambda *a, **kw: sum(j.state in ("queued", "loading") for j in jobs))
    return runner, events


class ContinuationTests(unittest.TestCase):
    def test_one_callback_loads_multiple_steps_and_stops_on_completion(self):
        job, chunk = prepared(2500)
        runner, events = queue(job)
        with patch.object(module, "perf_counter", return_value=0):
            Snapshot._cron_process(runner)
        self.assertEqual(job.loaded_invoices, 2500)
        self.assertEqual(job.state, "ready")
        self.assertEqual(events["notifications"], [{"done": 5, "remaining": 0}])
        self.assertFalse(events["wakeups"])

    def test_step_limit_returns_control_with_saved_cursor_and_wakes_continuation(self):
        job, chunk = prepared(12000)
        runner, events = queue(job)
        with patch.object(module, "perf_counter", return_value=0):
            Snapshot._cron_process(runner)
        self.assertEqual((job.loaded_invoices, chunk.processed_count), (10000, 10000))
        self.assertFalse(chunk.loaded)
        self.assertEqual(events["notifications"], [{"done": 20, "remaining": 1}])
        self.assertEqual(events["wakeups"], [job.id])
        with patch.object(module, "perf_counter", return_value=0):
            Snapshot._cron_process(runner)
        self.assertEqual(job.state, "ready")
        keys = [r["invoice_key"] for r in job.env.invoices.created_values]
        self.assertEqual(keys, [str(i) for i in range(12000)])
        self.assertEqual(events["wakeups"], [job.id])

    def test_elapsed_budget_stops_between_complete_steps(self):
        job, chunk = prepared(2500)
        runner, events = queue(job)
        clock = [0.0]; original = job._run_import_step
        def step():
            result = original(); clock[0] += 3.1; return result
        job._run_import_step = step
        with patch.object(module, "perf_counter", side_effect=lambda: clock[0]):
            Snapshot._cron_process(runner)
        self.assertEqual((job.loaded_invoices, chunk.processed_count), (1000, 1000))
        self.assertEqual(events["notifications"], [{"done": 2, "remaining": 1}])
        self.assertEqual(events["wakeups"], [job.id])

    def test_slow_first_step_is_saved_without_starting_another(self):
        job, chunk = prepared(2500)
        runner, events = queue(job)
        clock = [0.0]; original = job._run_import_step
        def step():
            result = original(); clock[0] += 15; return result
        job._run_import_step = step
        with patch.object(module, "perf_counter", side_effect=lambda: clock[0]):
            Snapshot._cron_process(runner)
        self.assertEqual(job.loaded_invoices, 500)
        self.assertEqual(events["notifications"], [{"done": 1, "remaining": 1}])
        self.assertEqual(events["wakeups"], [job.id])

    def test_preparation_returns_immediately_and_wakes_loading(self):
        job = Job(); runner, events = queue(job)
        job._prepare = lambda: job.write({"state": "loading", "total_invoices": 1})
        job._load_next = lambda: self.fail("Preparation must commit before loading")
        Snapshot._cron_process(runner)
        self.assertEqual(job.state, "loading")
        self.assertEqual(events["wakeups"], [job.id])

    def test_all_locked_sources_never_spin_or_schedule_more_work(self):
        job = Job(); job.env.cr.lock = False
        runner, events = queue(job)
        job._run_import_step = lambda: self.fail("Locked source")
        Snapshot._cron_process(runner)
        self.assertFalse(events["wakeups"])
        self.assertEqual(events["notifications"], [{"done": 0, "remaining": 1}])

    def test_no_jobs_does_not_try_to_wake_an_unbound_snapshot(self):
        job = Job(); job.state = "ready"; runner, events = queue(job)
        Snapshot._cron_process(runner)
        self.assertEqual(events["notifications"], [{"done": 0, "remaining": 0}])
        self.assertFalse(events["wakeups"])

    def test_missing_progress_breaks_loop_instead_of_running_twenty_times(self):
        job = Job(); job.state = "loading"; job.total_invoices = 1
        runner, events = queue(job); calls = []
        job._run_import_step = lambda: (calls.append(1) or True)
        Snapshot._cron_process(runner)
        self.assertEqual(len(calls), 1)

    def test_validation_failure_does_not_publish_or_repeat_the_failed_step(self):
        job, chunk = prepared(2500)
        runner, events = queue(job); original = job._load_next
        def load():
            if job.loaded_invoices == 1000: raise ValueError("Invalid source record")
            return original()
        job._load_next = load
        with patch.object(module, "perf_counter", return_value=0), self.assertLogs(module._logger, level="ERROR"):
            Snapshot._cron_process(runner)
        self.assertEqual(job.loaded_invoices, 1000)
        self.assertEqual(chunk.processed_count, 1000)
        self.assertEqual(job.state, "error")
        self.assertFalse(job.source_id.active_snapshot_id)
        self.assertFalse(events["wakeups"])

    def test_finished_source_wakes_other_queued_work(self):
        job, chunk = prepared(2)
        other = Job(); other.id = 77
        runner, events = queue(job, [other])
        Snapshot._cron_process(runner)
        self.assertEqual(job.state, "ready")
        self.assertEqual(other.state, "queued")
        self.assertEqual(events["wakeups"], [job.id])

    def test_notification_failure_preserves_load_and_continuation(self):
        job, chunk = prepared(1500); runner, events = queue(job)
        def fail(**kw): raise RuntimeError("Progress API unavailable")
        job.env.models["ir.cron"] = SimpleNamespace(_notify_progress=fail)
        with patch.object(module, "CRON_MAX_STEPS", 1), self.assertLogs(module._logger, level="WARNING"):
            Snapshot._cron_process(runner)
        self.assertEqual((job.loaded_invoices, chunk.processed_count), (500, 500))
        self.assertEqual(events["wakeups"], [job.id])

    def test_trigger_failure_does_not_discard_already_processed_invoices(self):
        job, chunk = prepared(1500); runner, events = queue(job)
        job._schedule_import = Snapshot._schedule_import.__get__(job)
        def fail(): raise RuntimeError("Trigger unavailable")
        cron = SimpleNamespace(active=True, _trigger=fail); cron.sudo = lambda: cron
        job.env.ref = lambda *a, **kw: cron
        with patch.object(module, "CRON_MAX_STEPS", 1), self.assertLogs(module._logger, level="WARNING"):
            Snapshot._cron_process(runner)
        self.assertEqual((job.loaded_invoices, chunk.processed_count), (500, 500))
        self.assertEqual(job.state, "loading")


if __name__ == "__main__": unittest.main()
