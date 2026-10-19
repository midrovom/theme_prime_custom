from odoo import fields, models


class TCTransport(models.Model):
    _name = 'tc.transport'
    _description = 'Transportista Transcash'
    _rec_name = 'name'
    _sql_constraints = [('ruc_uniq', 'unique(company_id, ruc)', 'El RUC del transportista ya existe.')]
    name = fields.Char(required=True)
    ruc = fields.Char(required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True, ondelete='cascade')


class TCDriver(models.Model):
    _name = 'tc.driver'
    _description = 'Chofer Transcash'
    _sql_constraints = [('ident_uniq', 'unique(company_id, identification)', 'La identificación del chofer ya existe.')]
    name = fields.Char(required=True)
    identification = fields.Char(required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True, ondelete='cascade')


class TCAddress(models.Model):
    _name = 'tc.address'
    _description = 'Ubicación o tercero logístico'
    _sql_constraints = [('code_kind_uniq', 'unique(company_id, kind, external_code)', 'El código ya existe para esta entidad.')]
    name = fields.Char(required=True)
    kind = fields.Selection([('sender', 'Remitente'), ('recipient', 'Destinatario'), ('destination', 'Destino')], required=True)
    external_code = fields.Char(required=True, index=True)
    address = fields.Char()
    city = fields.Char()
    company_id = fields.Many2one('res.company', required=True, index=True, ondelete='cascade')


class TCVehicle(models.Model):
    _name = 'tc.vehicle'
    _description = 'Vehículo Transcash'
    _sql_constraints = [('plate_uniq', 'unique(company_id, plate)', 'Esta placa ya existe.')]
    name = fields.Char(compute='_compute_name')
    plate = fields.Char(required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True, ondelete='cascade')

    def _compute_name(self):
        for rec in self:
            rec.name = rec.plate or ''


class TCProduct(models.Model):
    _name = 'tc.product'
    _description = 'Referencia de producto ERP para logística'
    _sql_constraints = [('sku_uniq', 'unique(company_id, sku)', 'El SKU ya existe.')]
    name = fields.Char(required=True)
    sku = fields.Char(required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True, ondelete='cascade')


class TCBrand(models.Model):
    _name = 'tc.product.brand'
    _description = 'Marca de producto - Privado'
    _sql_constraints = [('code_uniq', 'unique(company_id, code)', 'La marca ya existe.')]
    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True, ondelete='cascade')


class TCProductSupplier(models.Model):
    _name = 'tc.product.supplier'
    _description = 'Proveedor de producto - Privado'
    _sql_constraints = [('taxid_uniq', 'unique(company_id, tax_id)', 'La identificación fiscal del proveedor ya existe.')]
    name = fields.Char(required=True)
    tax_id = fields.Char(required=True, index=True)
    external_code = fields.Char()
    company_id = fields.Many2one('res.company', required=True, index=True, ondelete='cascade')


class TCGuide(models.Model):
    _name = 'tc.guide'
    _description = 'Guía importada del ERP'
    _order = 'id desc'
    _sql_constraints = [('external_uniq', 'unique(company_id, external_id)', 'La guía ERP ya existe.')]

    company_id = fields.Many2one('res.company', required=True, index=True, ondelete='cascade')
    external_id = fields.Char(required=True, index=True)
    name = fields.Char(required=True, index=True, string='Número de guía')
    document_type = fields.Char()
    document_number = fields.Char()
    erp_state = fields.Char()
    transport_id = fields.Many2one('tc.transport', ondelete='restrict')
    transport_name = fields.Char(string='Transportista recibido')
    driver_id = fields.Many2one('tc.driver', ondelete='restrict')
    vehicle_id = fields.Many2one('tc.vehicle', ondelete='restrict')
    sender_id = fields.Many2one('tc.address', ondelete='restrict')
    recipient_id = fields.Many2one('tc.address', ondelete='restrict')
    destination_id = fields.Many2one('tc.address', ondelete='restrict')
    origin_address = fields.Char()
    destination_address = fields.Char()
    destination_city = fields.Char()
    erp_start_date = fields.Date()
    erp_end_date = fields.Date()
    erp_planned_date = fields.Date()
    cargo_description = fields.Text()
    line_ids = fields.One2many('tc.guide.line', 'guide_id', string='Productos')
    last_sync = fields.Datetime(readonly=True)


class TCGuideLine(models.Model):
    _name = 'tc.guide.line'
    _description = 'Línea de guía ERP (operativa)'
    _sql_constraints = [('line_uniq', 'unique(guide_id, external_line_id)', 'La línea ya existe en esta guía.')]
    guide_id = fields.Many2one('tc.guide', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='guide_id.company_id', store=True, index=True)
    external_line_id = fields.Char(required=True)
    product_id = fields.Many2one('tc.product', ondelete='restrict')
    sku = fields.Char(required=True)
    name = fields.Char(required=True)
    quantity = fields.Float(digits=(16, 4))
    weight_kg = fields.Float(digits=(16, 4))
    pallets = fields.Float(digits=(16, 4))
    boxes = fields.Float(digits=(16, 4))
    private_id = fields.One2many('tc.guide.line.private', 'line_id', string='Datos comerciales restringidos', groups='transcash_guias_api.group_tc_sync_admin')


class TCGuideLinePrivate(models.Model):
    _name = 'tc.guide.line.private'
    _description = 'Información comercial privada de línea ERP'
    _sql_constraints = [('private_line_uniq', 'unique(line_id)', 'Solo puede existir un registro privado por línea.')]
    line_id = fields.Many2one('tc.guide.line', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', related='line_id.company_id', store=True, index=True)
    brand_id = fields.Many2one('tc.product.brand', ondelete='restrict')
    supplier_id = fields.Many2one('tc.product.supplier', ondelete='restrict')
    supplier_code_raw = fields.Char()
    supplier_reference_raw = fields.Char()
    supplier_name_raw = fields.Char()
    supplier_tax_raw = fields.Char()
    brand_code_raw = fields.Char()
    brand_name_raw = fields.Char()


class TCSyncLog(models.Model):
    _name = 'tc.guide.sync.log'
    _description = 'Resultados de sincronización de guías'
    _order = 'id desc'
    company_id = fields.Many2one('res.company', required=True, index=True, ondelete='cascade')
    api_name = fields.Char(default='getguiaslogistica')
    date = fields.Datetime(default=fields.Datetime.now)
    created_count = fields.Integer()
    updated_count = fields.Integer()
    error_count = fields.Integer()
    details = fields.Text()
