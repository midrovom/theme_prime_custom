"""Business-key, update and weight reconciliation regression cases."""
import unittest
from test_engine_standalone import e, line, inv


class UniquenessTests(unittest.TestCase):
    def test_business_key_uses_external_not_internal_or_type(self):
        first=line(TipoFactura=" fa ",NumeroFactura=" 100 ")
        second=line(Establecimiento="Otro",CodBodega="OTRA",NumeroFactura="999",TipoFactura="NC")
        self.assertEqual(e.invoice_key(first),e.invoice_key(second))
        self.assertNotEqual(e.invoice_key(first),e.invoice_key(line(Factura="999")))

    def test_display_and_prefix(self):
        for external in ("001-001-000000123", " FAC/001-001-000000123 "):
            summary=inv([line(Factura=external)])
            self.assertEqual(summary["name"], "FAC/001-001-000000123")
            self.assertEqual(summary["external_number"], "001-001-000000123")
            self.assertEqual(summary["invoice_key"], '["FAC","001-001-000000123"]')

    def test_missing_external_is_explicit_and_never_collides(self):
        raw=line(Factura="")
        self.assertIn("SIN NÚMERO EXTERNO", inv([raw])["name"])
        self.assertNotEqual(e.invoice_key(raw), e.invoice_key(line(Factura="100")))
        self.assertNotEqual(e.invoice_key(raw), e.invoice_key(line(Factura="",NumeroFactura="101")))

    def test_external_grouping_across_internal_numbers(self):
        rows=[line(), line(NumeroFactura="200",CodBodega="B2"), line(Factura="002-1")]
        groups=dict(e.iter_invoice_groups(rows))
        self.assertEqual(sorted(map(len,groups.values())),[1,2])
        self.assertEqual(len(e.unique_invoice_lines(groups[e.invoice_key(rows[0])])[0]),2)

    def test_current_external_winner_per_company(self):
        base={"id":1,"company_id":1,"invoice_type":"FA","internal_number":"1","external_number":"001", "cutoff_date":"2026-10-29","snapshot_id":1}
        rows=[base,{**base,"id":2,"internal_number":"99","snapshot_id":2},
              {**base,"id":3,"external_number":"002"},{**base,"id":4,"company_id":2}]
        self.assertEqual(set(e.latest_invoice_versions(rows)),{2,3,4})

    def test_identical_repeated_details_are_not_added(self):
        rows=[line(PesoPendiente=9000),line(PesoPendiente=9000)]
        unique,removed,updated=e.unique_invoice_lines(rows)
        self.assertEqual((len(unique),removed,updated),(1,1,0))
        self.assertEqual(inv(unique)["pending_weight"],9000)

    def test_last_observation_updates_quantities_instead_of_summing(self):
        rows=[line(Pendiente=10,PesoPendiente=9000),line(Pendiente=4,DespachoFisico=6,PesoPendiente=3600,UltimoDespacho="2026-10-02")]
        unique,removed,updated=e.unique_invoice_lines(rows)
        self.assertEqual((len(unique),removed,updated),(1,1,1))
        self.assertEqual(inv(unique)["pending_weight"],3600)

    def test_distinct_warehouse_and_product_rows_are_preserved(self):
        rows=[line(),line(CodBodega="B2"),line(CodProducto="P2")]
        self.assertEqual(len(e.unique_invoice_lines(rows)[0]),3)
        self.assertEqual(len(list(e.iter_invoice_groups(rows))),1)

    def test_double_import_has_one_current_record_per_key(self):
        rows=[{"id":i,"company_id":1,"invoice_type":"FA","internal_number":str(n),"cutoff_date":"2026-10-29","snapshot_id":snapshot}
            for i,(n,snapshot) in enumerate(((1,1),(2,1),(1,2),(2,2)),1)]
        self.assertEqual(set(e.latest_invoice_versions(rows)),{3,4})

    def test_same_business_key_in_different_companies_is_distinct(self):
        base={"id":1,"company_id":1,"invoice_type":"FA","internal_number":"1","cutoff_date":"2026-10-29","snapshot_id":1}
        self.assertEqual(len(e.latest_invoice_versions([base,{**base,"id":2,"company_id":2}])),2)

    def test_older_cutoff_cannot_win_by_later_upload_id(self):
        base={"id":1,"company_id":1,"invoice_type":"FA","internal_number":"1","cutoff_date":"2026-10-29","snapshot_id":1}
        older={**base,"id":99,"snapshot_id":99,"cutoff_date":"2026-10-28"}
        self.assertEqual(e.latest_invoice_versions([base,older]),[1])

    def test_type_is_part_of_key_and_whitespace_is_normalized(self):
        base={"id":1,"company_id":1,"invoice_type":"FA","internal_number":"1","cutoff_date":"2026-10-29","snapshot_id":1}
        rows=[base,{**base,"id":2,"invoice_type":" fa ","internal_number":" 1 ","snapshot_id":2},
              {**base,"id":3,"invoice_type":"NC"}]
        self.assertEqual(set(e.latest_invoice_versions(rows)),{2,3})

    def test_billed_weight_conservation_without_adjustments(self):
        result=e.weight_metrics(line(DespachoFisico=4,Pendiente=6,PesoDespacho=8000,PesoPendiente=12000))
        self.assertEqual(result["invoiced_weight"],20000)
        self.assertTrue(result["invoiced_weight_available"])

    def test_adjustment_without_weight_does_not_fabricate_billed_tonnes(self):
        result=e.weight_metrics(line(DespachoFisico=4,Pendiente=5,AjusteDevolucion=1,PesoDespacho=8000,PesoPendiente=12000))
        self.assertFalse(result["invoiced_weight_available"])
        self.assertEqual(result["invoiced_weight"],0)
        self.assertEqual(result["dispatched_weight"],8000)

    def test_explicit_billed_or_adjustment_weight_is_supported(self):
        values=line(DespachoFisico=4,Pendiente=5,AjusteDevolucion=1,PesoDespacho=8000,PesoPendiente=12000)
        self.assertEqual(e.weight_metrics({**values,"PesoFacturado":24000})["invoiced_weight"],24000)
        self.assertEqual(e.weight_metrics({**values,"PesoAjusteDevolucion":4000})["invoiced_weight"],24000)

    def test_positive_pending_without_weight_is_unknown_for_billed_indicator(self):
        metrics=e.weight_metrics(line(PesoPendiente=0))
        self.assertFalse(metrics["invoiced_weight_available"])

    def test_absent_dispatched_weight_is_not_inferred_from_quantities(self):
        metrics=e.weight_metrics(line(DespachoFisico=4,Pendiente=6,PesoPendiente=12000))
        self.assertFalse(metrics["dispatched_weight_available"])
        self.assertFalse(metrics["invoiced_weight_available"])

    def test_three_tonnage_metrics_remain_separate(self):
        invoice=inv([line(DespachoFisico=4,Pendiente=6,PesoDespacho=8000,PesoPendiente=12000,UltimoDespacho="2026-10-02")])
        stats=e.summarize([invoice])
        self.assertEqual((stats["invoiced_tons"],stats["dispatched_tons"],stats["pending_tons"]),(20,8,12))

    def test_old_prepared_block_uses_new_key_and_weight_fields(self):
        from test_import_queue_standalone import Job
        raw=line(PesoPendiente=9000,PesoDespacho=0)
        summary=inv([raw])
        summary["invoice_key"]='["FA","100","Old establishment"]'
        for key in ("invoiced_weight","dispatched_weight","invoiced_weight_missing_rows","dispatched_weight_missing_rows"):
            summary.pop(key,None)
        values=Job()._invoice_values({"summary":summary,"lines":[raw]}, {"B1":10})
        self.assertEqual(values["invoice_key"],'["FAC","001-1"]')
        self.assertEqual(values["invoiced_weight"],9000)
        self.assertEqual(values["line_ids"][0][2]["warehouse_id"],10)

    def test_old_prepared_duplicate_detail_is_consolidated_when_resuming(self):
        from test_import_queue_standalone import Job
        raw=line(PesoPendiente=9000,PesoDespacho=0)
        summary=inv([raw,raw])
        summary["invoice_key"]='["FA","100","Old establishment"]'
        values=Job()._invoice_values({"summary":summary,"lines":[raw,raw]}, {"B1":10})
        self.assertEqual(len(values["line_ids"]),1)
        self.assertEqual(values["pending_weight"],9000)


if __name__=="__main__":unittest.main()
