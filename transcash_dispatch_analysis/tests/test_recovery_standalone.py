"""Resume persisted import cursors and keep heavy work outside browser RPC."""
import base64
import json
from types import SimpleNamespace
import unittest

from test_import_queue_standalone import Job, FakeAccessError, module


def prepared(count, details=1):
    job=Job();job.state="loading";job.total_invoices=count;job.total_rows=count*details
    data=[{"key":str(i),"lines":[{} for _ in range(details)]} for i in range(count)]
    job._invoice_values=lambda item,warehouse_map=None:{"invoice_key":item["key"],"line_ids":[(0,0,{}) for _ in item["lines"]]}
    chunk=job.env.chunks.create({"snapshot_id":job.id,"phase":"prepared","sequence":0,"row_count":count,
        "payload":base64.b64encode(json.dumps(data).encode())})
    return job,chunk


class RecoveryTests(unittest.TestCase):
    def test_old_large_prepared_chunk_commits_a_bounded_prefix_and_resumes(self):
        job,chunk=prepared(250)
        first=job.process_import_step()
        self.assertEqual((first["loaded_invoices"],chunk.processed_count),(100,100))
        self.assertEqual(first["state"],"loading");self.assertFalse(chunk.loaded)
        # Represents a new read after a response was lost: the persisted cursor
        # is authoritative, not the amount the browser last displayed.
        self.assertEqual(job._progress_payload()["loaded_invoices"],100)
        second=job.process_import_step()
        self.assertEqual((second["loaded_invoices"],chunk.processed_count),(200,200))
        last=job.process_import_step()
        self.assertTrue(last["done"])
        keys=[r["invoice_key"] for r in job.env.invoices.created_values]
        self.assertEqual(keys,[str(i) for i in range(250)])
        self.assertEqual(len(keys),len(set(keys)))

    def test_many_detail_lines_reduce_invoice_count_per_step(self):
        job,chunk=prepared(3,300)
        job.process_import_step()
        self.assertEqual(job.loaded_invoices,1)
        self.assertEqual(chunk.processed_count,1)
        self.assertEqual(job.env.invoices.line_count,300)

    def test_one_invoice_is_never_split_across_commits(self):
        job,chunk=prepared(2,600)
        job.process_import_step()
        self.assertEqual(job.loaded_invoices,1)
        self.assertEqual(job.env.invoices.line_count,600)
        self.assertFalse(chunk.loaded)

    def test_invalid_cursor_fails_before_creating_invoices(self):
        for cursor in (-1,3,4):
            job,chunk=prepared(3);chunk.processed_count=cursor
            with self.assertLogs(module._logger,level="ERROR"):
                result=job.process_import_step()
            self.assertTrue(result["failed"])
            self.assertEqual(job.env.invoices.count,0)

    def test_background_request_only_schedules_the_existing_job(self):
        job=Job();scheduled=[]
        cron=SimpleNamespace(active=True);cron.sudo=lambda:cron
        job.env.ref=lambda *a,**kw:cron
        job._schedule_import=lambda:scheduled.append(job.id)
        job._prepare=lambda:self.fail("Heavy preparation cannot run in a scheduling RPC")
        progress=job.request_background_processing()
        self.assertEqual(scheduled,[job.id])
        self.assertTrue(progress["background_processing"])
        self.assertEqual(progress["state"],"queued")

    def test_disabled_cron_keeps_interactive_fallback_and_does_not_schedule(self):
        job=Job()
        job._schedule_import=lambda:self.fail("A disabled cron must not be triggered")
        result=job.request_background_processing()
        self.assertFalse(result["background_processing"])

    def test_background_rpc_checks_operator_before_elevation(self):
        job=Job();job.authorized=False
        with self.assertRaises(FakeAccessError):job.request_background_processing()
        self.assertEqual(job.sudo_calls,0)

    def test_finished_snapshot_does_not_schedule_work_again(self):
        job=Job();job.state="ready"
        cron=SimpleNamespace(active=True);cron.sudo=lambda:cron
        job.env.ref=lambda *a,**kw:cron
        job._schedule_import=lambda:self.fail("A completed load is already published")
        self.assertTrue(job.request_background_processing()["done"])


if __name__=="__main__":unittest.main()
