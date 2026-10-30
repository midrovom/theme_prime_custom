"""Fast intake parity and bounded, adaptive background work."""
import base64
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_import_queue_standalone import Job, Snapshot, module
from test_recovery_standalone import prepared
from test_api_sync_standalone import adapter, line, Source
from dispatch_queue_test.services.engine import iter_invoice_groups, unique_invoice_lines
from dispatch_queue_test.services.import_optimization import (
    background_limits, next_background_size, iter_presorted_invoice_groups)


class GroupingTests(unittest.TestCase):
    def grouped(self, rows):
        return [row for chunk in adapter.iter_api_chunks(rows, group_invoices=True) for row in chunk]

    def test_streaming_matches_general_grouping_with_interleaved_updates(self):
        rows = [line(NumeroFactura="0002"), line(), line(CodBodega="B2"),
            line(TipoFactura="NC"), line(Pendiente=4, PesoPendiente=4000),
            line(NumeroFactura="0002", CodProducto="P2")]
        normalized = adapter.convert_dispatch_payload(rows, "2026-10-29")["rows"]
        expected = list(iter_invoice_groups(normalized))
        actual = list(iter_presorted_invoice_groups(self.grouped(normalized)))
        self.assertEqual(actual, expected)
        unique, removed, changed = unique_invoice_lines(actual[0][1])
        self.assertEqual((removed, changed), (1, 1))
        self.assertEqual(len(unique), 2)
        self.assertEqual(unique[0]["PesoPendiente"], 4000)

    def test_repeated_details_remain_together_across_raw_chunk_boundary(self):
        rows = [line(NumeroFactura="B"), line(NumeroFactura="A"),
                line(NumeroFactura="A", Pendiente=4, PesoPendiente=4000)]
        size = len(json.dumps(rows[0], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
        with patch.object(adapter, "MAX_CHUNK_BYTES", size * 2):
            chunks = list(adapter.iter_api_chunks(rows, group_invoices=True))
        self.assertEqual([len(c) for c in chunks], [1, 1, 1])
        groups = list(iter_presorted_invoice_groups(row for chunk in chunks for row in chunk))
        self.assertEqual([len(group) for _, group in groups], [2, 1])
        self.assertEqual(unique_invoice_lines(groups[0][1])[0][0]["PesoPendiente"], 4000)

    def test_disordered_marker_is_rejected_instead_of_splitting_invoice(self):
        with self.assertRaisesRegex(ValueError, "secuencia API"):
            list(iter_presorted_invoice_groups([line(NumeroFactura="B"), line(NumeroFactura="A")]))

    def test_empty_non_object_and_bad_invoice_key(self):
        self.assertEqual(list(iter_presorted_invoice_groups([])), [])
        for rows in ([None], [line(NumeroFactura=None)]):
            with self.assertRaises(ValueError): list(iter_presorted_invoice_groups(rows))

    def test_new_pull_marks_only_stably_grouped_intake(self):
        source = Source()
        result = source.pull([line(NumeroFactura="B"), line(), line(Pendiente=4)])
        self.assertEqual(result["snapshot_id"], 1)
        snapshot = source.snapshots.rows[0]
        self.assertTrue(snapshot.api_grouped_rows)
        rows = [row for chunk in snapshot.chunks for row in chunk]
        self.assertEqual([r["NumeroFactura"] for r in rows], ["0001", "0001", "B"])
        self.assertEqual([r["Pendiente"] for r in rows[:2]], [10, 4])

    def test_fast_prepare_avoids_sqlite_and_keeps_totals_and_city_policies(self):
        rows = [line(NumeroFactura="B", Ciudad="Cuenca"), line(), line(Pendiente=4, PesoPendiente=4000)]
        job = Job(); job.input_type = "api"; job.api_grouped_rows = True; job.total_rows = len(rows)
        job._rows = lambda: iter(self.grouped(rows))
        with patch.object(module, "iter_invoice_groups", side_effect=AssertionError("No temporary SQLite for grouped pull")):
            job._prepare()
        job._load_next()
        self.assertEqual((job.total_invoices, job.duplicate_rows, job.duplicate_updates), (2, 1, 1))
        self.assertEqual(job.env.invoices.sla_days_counts, {"GUAYAQUIL": {3}, "CUENCA": {9}})
        self.assertEqual(sum(r["pending_weight"] for r in job.env.invoices.created_values), 14000)

    def test_old_api_intake_still_uses_general_grouping(self):
        rows = [line(NumeroFactura="B"), line()]
        job = Job(); job.input_type = "api"; job.total_rows = len(rows); job._rows = lambda: iter(rows)
        with patch.object(module, "iter_invoice_groups", wraps=module.iter_invoice_groups) as general:
            job._prepare()
        general.assert_called_once()
        self.assertEqual(job.total_invoices, 2)

    def test_repeated_column_aliases_resolve_once_without_changing_conflict_checks(self):
        rows = [line(NumeroFactura=str(i)) for i in range(200)]
        with patch.object(adapter, "_key", wraps=adapter._key) as key:
            dataset = adapter.convert_dispatch_payload(rows, "2026-10-29")
        self.assertEqual(key.call_count, len(rows[0]))
        self.assertEqual(len(dataset["rows"]), 200)
        with self.assertRaises(adapter.DispatchAPIError):
            adapter.convert_dispatch_payload([dict(line(), peso_pendiente=1)], "2026-10-29")


class BatchTests(unittest.TestCase):
    def test_limits_and_adaptation_have_hard_bounds(self):
        self.assertEqual(background_limits(0), (500, 2500))
        self.assertEqual(background_limits(50000), (500, 2500))
        self.assertEqual(background_limits(-1), (50, 250))
        self.assertEqual(next_background_size(500, 500, 15), 100)
        self.assertEqual(next_background_size(100, 100, 0.1), 200)
        self.assertEqual(next_background_size(500, 500, 120), 50)
        self.assertEqual(next_background_size(500, 500, 0.01), 500)
        self.assertEqual(next_background_size(100, 100, 0), 100)
        self.assertEqual(next_background_size(100, 0, 5), 100)

    def test_short_tail_does_not_shrink_a_healthy_batch(self):
        self.assertEqual(next_background_size(500, 10, 1), 500)

    def test_background_resumes_existing_chunk_in_one_500_invoice_step(self):
        job, chunk = prepared(500)
        job.with_context(dispatch_background=True)
        job.process_import_step()
        self.assertEqual(job.loaded_invoices, 500)
        self.assertEqual(job.state, "ready")
        self.assertEqual(len(job.env.invoices.created_values), 500)

    def test_background_cursor_resumes_after_interactive_prefix(self):
        job, chunk = prepared(500)
        job.process_import_step()
        self.assertEqual(chunk.processed_count, 100)
        job.with_context(dispatch_background=True)
        job.process_import_step()
        self.assertEqual(job.loaded_invoices, 500)
        self.assertEqual([r["invoice_key"] for r in job.env.invoices.created_values], [str(i) for i in range(500)])

    def test_adaptive_smaller_size_and_detail_budget_are_respected(self):
        job, chunk = prepared(100)
        job.with_context(dispatch_background=True); job.background_batch_size = 50
        job.process_import_step()
        self.assertEqual(chunk.processed_count, 50)
        job, chunk = prepared(4, 1000)
        job.with_context(dispatch_background=True)
        job.process_import_step()
        self.assertEqual(chunk.processed_count, 2)
        self.assertEqual(job.env.invoices.line_count, 2000)

    def test_exceptional_invoice_is_whole_in_background_too(self):
        job, chunk = prepared(2, 3000)
        job.with_context(dispatch_background=True); job.process_import_step()
        self.assertEqual(chunk.processed_count, 1)
        self.assertEqual(job.env.invoices.line_count, 3000)

    def test_slow_step_including_flush_reduces_next_background_batch(self):
        job, chunk = prepared(500)
        job.with_context(dispatch_background=True)
        with patch.object(module, "perf_counter", side_effect=[10, 25]):
            job.process_import_step()
        self.assertEqual(job.background_batch_size, 100)
        self.assertEqual(job.last_step_seconds, 15)

    def test_interactive_size_is_still_100_even_if_background_tuning_is_high(self):
        job, chunk = prepared(500)
        job.process_import_step()
        self.assertEqual(chunk.processed_count, 100)
        self.assertEqual(job.background_batch_size, 500)

    def test_cron_adds_background_context_and_retains_notify_context(self):
        job = Job(); seen = []
        job.env.context["ir_cron_progress_id"] = 99
        job._prepare = lambda: (seen.append(dict(job.env.context)), job.write({"state": "loading"}))
        notifications = []
        job.env.models["ir.cron"] = SimpleNamespace(_notify_progress=lambda **kw: notifications.append(kw))
        runner = SimpleNamespace(env=job.env, search=lambda *a, **k: [job], search_count=lambda *a, **k: 1)
        Snapshot._cron_process(runner)
        self.assertTrue(seen[0]["dispatch_background"])
        self.assertFalse(seen[0]["bin_size"])
        self.assertEqual(seen[0]["ir_cron_progress_id"], 99)
        self.assertEqual(notifications, [{"done": 1, "remaining": 1}])


if __name__ == "__main__": unittest.main()
