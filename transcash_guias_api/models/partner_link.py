"""Homologación segura de terceros del ERP con Contactos y los perfiles Portal v5.32.

No crea usuarios ni otorga grupos Portal: se mantienen las activaciones auditadas
por Logística Transcash. La importación es repetible (upsert por identidad).
"""
import logging
import re

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from .transport_identity import normalize_transport_ruc
from .fiscal_identity import (fiscal_document, fiscal_variants, fiscal_key,
                              create_fiscal_partner)

_logger = logging.getLogger(__name__)


def _clean(value):
    return str(value).strip() if value not in (None, False) else ''


def _identifier(value):
    """Normalización para cotejar identificaciones, NO validación tributaria."""
    return re.sub(r'[^A-Z0-9]', '', _clean(value).upper())


def _is_tax(value):
    # Los códigos logísticos como -NAJ y PRS3339 NO son documentos fiscales.
    return bool(re.fullmatch(r'[A-Z0-9]{10,15}', _identifier(value))) and bool(
        re.fullmatch(r'[A-Z0-9]{10,15}', _clean(value).upper().replace(' ', ''))
        or re.fullmatch(r'[0-9][0-9.\- ]{9,19}', _clean(value)))


class TCGuidePartnerLink(models.Model):
    _inherit = 'tc.guide'

    transport_partner_id = fields.Many2one('res.partner', string='Transportista Odoo', readonly=True, copy=False)
    driver_partner_id = fields.Many2one('res.partner', string='Contacto del chofer', readonly=True, copy=False)
    sender_partner_id = fields.Many2one('res.partner', string='Remitente Odoo', readonly=True, copy=False)
    recipient_partner_id = fields.Many2one('res.partner', string='Destinatario Odoo', readonly=True, copy=False)
    driver_user_id = fields.Many2one('res.users', string='Portal chofer autorizado', readonly=True, copy=False)
    transport_tax_raw = fields.Char(string='Identificación de transportista ERP', readonly=True)
    recipient_tax_raw = fields.Char(string='Identificación del destinatario ERP', readonly=True)
    master_link_state = fields.Selection([
        ('complete', 'Vínculos verificados'),
        ('pending', 'Pendiente de vinculación'),
    ], string='Vínculos con el portal', default='pending', readonly=True, copy=False, index=True)
    master_link_note = fields.Text(string='Pendientes / observaciones de accesos', readonly=True, copy=False)

    def _partner_by_tax(self, tax):
        """Búsqueda global por identificación normalizada, incluidos archivados.

        No crea duplicados en otras compañías y no confunde VAT con ref ERP.
        """
        self.ensure_one()
        variants = fiscal_variants(tax)
        if not variants:
            return False, ''
        self.env.cr.execute('''
            SELECT id FROM res_partner
             WHERE UPPER(REGEXP_REPLACE(COALESCE(vat, ''), '[^A-Za-z0-9]', '', 'g')) = ANY(%s)
             ORDER BY id
        ''', (list(variants),))
        ids = [row[0] for row in self.env.cr.fetchall()]
        if not ids:
            return False, ''
        Partner = self.env['res.partner'].sudo().with_context(active_test=False)
        matches = Partner.browse(ids)
        allowed = matches.filtered(lambda p: not p.company_id or p.company_id.id == self.company_id.id)
        if not allowed:
            return False, _('La identificación %s pertenece a un contacto privado de otra compañía. No se duplica.') % tax
        linked = set(self.env['res.users'].sudo().with_context(active_test=False).search([
            ('partner_id', 'in', allowed.ids)]).mapped('partner_id').ids)
        ordered = allowed.sorted(key=lambda p: (
            not p.active, p.id not in linked, bool(p.company_id), p.id,
        ))
        chosen = ordered[0]
        if not chosen.active:
            return False, _('La identificación %s corresponde a un contacto archivado. Reactive el contacto existente.') % tax
        note = (_('Identificación %s: existen %s contactos duplicados; se reutiliza el contacto %s. '
                  'Revise Consolidación de terceros.') % (tax, len(matches), chosen.id)
                if len(matches) > 1 else '')
        return chosen, note

    def _partner_by_ref(self, code):
        self.ensure_one()
        code = _clean(code)
        Partner = self.env['res.partner'].sudo().with_context(active_test=False)
        matches = Partner.search([
            ('ref', '=', code), '|', ('company_id', '=', False),
            ('company_id', '=', self.company_id.id),
        ]) if code else Partner.browse()
        if not matches:
            return False, ''
        if len(matches) > 1:
            vats = {_identifier(p.vat) for p in matches if p.vat}
            if len(vats) > 1:
                return False, _('Código ERP %s pertenece a contactos con RUC diferentes.') % code
            linked = set(self.env['res.users'].sudo().with_context(active_test=False).search([
                ('partner_id', 'in', matches.ids)]).mapped('partner_id').ids)
            matches = matches.sorted(key=lambda p: (
                p.id not in linked, not p.active, bool(p.company_id), p.id,
            ))
            return matches[0], (_('Referencia ERP %s duplicada; se conserva el contacto %s.') %
                                (code, matches[0].id))
        return matches, ''

    def _resolve_transport_partner(self, name, raw_tax):
        """Contacto del transportista a pagar: búsqueda por documento antes de crear.

        RUC ecuatoriano (13 dígitos) se intenta como RUC. Si la validación
        falla, identificación extranjera. Nunca se recrea el mismo documento.
        """
        self.ensure_one()
        name = _clean(name)
        raw_tax = _clean(raw_tax)
        document = fiscal_document(raw_tax)
        Partner = self.env['res.partner'].sudo().with_context(active_test=False)

        if document and len(document) < 5:
            return False, _('Documento del transportista demasiado corto; no se creó contacto.')
        if document:
            # Bloqueo global: mismo documento, independientemente de compañía.
            self.env.cr.execute(
                'SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))',
                ('tc.party.identity', document))
            existing, note = self._partner_by_tax(document)
            if existing:
                # No modificar el VAT/tipo fiscal de contactos con historia.
                if 'supplier_rank' in Partner._fields and existing.supplier_rank < 1:
                    existing.write({'supplier_rank': 1})
                return existing, note
            if note:
                return False, note

        # Con nombre solo NO se crea una empresa: se busca un registro único
        # existente, y nunca se sobreescribe un VAT distinto.
        key = ' '.join(name.upper().split())
        matches = (Partner.search([('is_company', '=', True), ('name', '=ilike', name)])
                   if name else Partner.browse())
        matches = matches.filtered(lambda p: ' '.join((p.name or '').upper().split()) == key)
        allowed = matches.filtered(lambda p: not p.company_id or p.company_id.id == self.company_id.id)
        if matches and not allowed:
            return False, _('El transportista ya existe en otra compañía privada; no se duplicó.')
        if allowed and not allowed.filtered('active'):
            return False, _('Transportista archivado; reactive el registro existente.')
        if document and allowed:
            # Un nombre NO es una identidad. Es habitual que el ERP envíe
            # etiquetas genéricas (p. ej. TRANSPORTE PROPORCIONADO POR CLIENTE)
            # con identificaciones extranjeras distintas. No bloquear ni
            # vincular documentos diferentes porque comparten razón social.
            # El cotejo por VAT normalizado ya se realizó bajo advisory lock.
            blank = allowed.filtered(lambda p: p.active and not fiscal_key(p.vat))
            generic = key in {
                'TRANSPORTE PROPORCIONADO POR CLIENTE',
                'TRANSPORTE PROPORCIONADO POR EL CLIENTE',
            }
            if not generic and len(allowed) == 1 and len(blank) == 1:
                # Solo se puede completar el documento en una ficha activa,
                # inequívoca y sin identificación. Intentar tipo fiscal
                # preferente, y extranjera si no corresponde.
                values = {'vat': document}
                from .fiscal_identity import _type_values, first_kind
                preferred = first_kind(document, 'transport')
                try:
                    values.update(_type_values(
                        self.env, preferred,
                        require=(preferred == 'foreign' or
                                 'l10n_latam_identification_type_id' in Partner._fields)))
                    with self.env.cr.savepoint():
                        blank.sudo().write(values)
                except (ValidationError, UserError):
                    values = {'vat': document}
                    values.update(_type_values(self.env, 'foreign', require=True))
                    with self.env.cr.savepoint():
                        blank.sudo().write(values)
                if 'supplier_rank' in Partner._fields and blank.supplier_rank < 1:
                    blank.sudo().write({'supplier_rank': 1})
                return blank, _('Se completó la identificación de un transportista existente.')
            # Existen fichas con ese nombre, pero con documentos distintos,
            # sin documento o con un nombre genérico: se crea una sola ficha
            # por el NUEVO documento. Reimportar reutiliza esa ficha por VAT.
            _logger.info(
                'Transportista ERP: nombre repetido, identificación diferente; '
                'se resolverá por documento normalizado. nombre=%s documento=%s',
                name, document)
        if not document:
            if len(allowed) == 1 and allowed.active:
                return allowed, _('Vínculo provisional por nombre; falta identificación ERP.')
            return False, _('Transportista sin identificación; no se crea empresa por nombre.')
        if not name:
            return False, _('Transportista con documento %s pero sin razón social.') % document

        vals = {'name': name, 'is_company': True, 'company_id': False}
        if 'supplier_rank' in Partner._fields:
            vals['supplier_rank'] = 1
        partner, kind, note = create_fiscal_partner(self.env, vals, document, 'transport')
        return partner, note

    def _upsert_contact(self, kind, name, tax='', code='', street='', company=False):
        """Reutilizar por cédula/RUC (incluso extranjeros) y luego código ERP."""
        self.ensure_one()
        name, code = _clean(name), _clean(code)
        document = fiscal_document(tax)
        if document and len(document) < 5:
            return False, _('Documento demasiado corto de %s: %s.') % (kind, document)
        if document:
            self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))',
                                ('tc.party.identity', document))
        partner, message = self._partner_by_tax(document) if document else (False, '')
        if message and not partner:
            return False, message
        if not partner and code:
            found, note = self._partner_by_ref(code)
            if found and document and found.vat and not (fiscal_variants(found.vat) & fiscal_variants(document)):
                return False, _('Código ERP %s asociado a una identificación diferente; no se duplica.') % code
            partner = found
            if note:
                message = (message + '\n' + note).strip()
        if not partner:
            if not document and not code:
                return False, _('Falta documento o código ERP de %s: %s.') % (kind, name or '-')
            if not name:
                return False, _('Falta nombre de %s para crear contacto.') % kind
            values = {'name': name, 'is_company': company, 'company_id': False}
            if code:
                values['ref'] = code
            if street:
                values['street'] = street
            if document:
                partner, kind_created, note = create_fiscal_partner(
                    self.env, values, document, 'driver' if kind == 'driver' else kind)
                if note:
                    message = (message + '\n' + note).strip()
            else:
                partner = self.env['res.partner'].sudo().create(values)
        else:
            if document and partner.vat and not (fiscal_variants(partner.vat) & fiscal_variants(document)):
                return False, _('Identificación incompatible con contacto %s (%s).') % (partner.id, kind)
            updates = {}
            if document and not partner.vat:
                # Evitar actualizar un contacto con información fiscal inválida.
                from .fiscal_identity import _type_values, first_kind
                preferred = first_kind(document, 'driver' if kind == 'driver' else kind)
                updates['vat'] = document
                # Tipo se establece dentro del savepoint para poder reintentar
                # un documento fiscal inválido como identificación extranjera.
            if code and not partner.ref:
                updates['ref'] = code
            if street and not partner.street:
                updates['street'] = street
            if updates:
                try:
                    if document and not partner.vat:
                        from .fiscal_identity import _type_values, first_kind
                        preferred = first_kind(document, 'driver' if kind == 'driver' else kind)
                        updates.update(_type_values(
                            self.env, preferred,
                            require=(preferred == 'foreign' or
                                     'l10n_latam_identification_type_id' in self.env['res.partner']._fields)))
                    with self.env.cr.savepoint():
                        partner.sudo().write(updates)
                except (ValidationError, UserError):
                    if not document or partner.vat:
                        raise
                    from .fiscal_identity import _type_values
                    updates.update(_type_values(self.env, 'foreign', require=True))
                    with self.env.cr.savepoint():
                        partner.sudo().write(updates)
        return partner, message

    def _resolve_driver_user(self, partner, transport=False):
        """Create Portal login once; logistics role is manually activated in v5.32."""
        self.ensure_one()
        if not partner:
            return False, _('Sin contacto del chofer para crear usuario Portal.')
        identification = _identifier(partner.vat)
        if not (identification.isdigit() and len(identification) in (10, 13)):
            return False, _('El chofer necesita una cédula/RUC numérica para crear el usuario.')
        User = self.env['res.users'].sudo().with_context(active_test=False)
        users = User.search([('partner_id', '=', partner.id)])
        if len(users) > 1:
            return False, _('Contacto chofer con varias cuentas; requiere revisión administrativa.')
        if users:
            user = users[0]
            if not user.active:
                return False, _('El usuario del chofer está archivado; no se creó otro.')
            if not user.share or not user.has_group('base.group_portal'):
                return False, _('El usuario existente no es Portal; no se convierte automáticamente.')
        else:
            same_login = User.search([('login', '=', identification)])
            if same_login:
                if len(same_login) != 1 or same_login.partner_id != partner:
                    return False, _('El login %s pertenece a otro contacto; no se modifica.') % identification
                user = same_login[0]
            else:
                group = self.env.ref('base.group_portal')
                user = User.with_context(no_reset_password=True, mail_create_nosubscribe=True,
                                         tracking_disable=True).create({
                    'name': partner.name, 'login': identification,
                    'partner_id': partner.id, 'password': identification,
                    'groups_id': [(6, 0, [group.id])],
                    'company_id': self.company_id.id,
                    'company_ids': [(6, 0, [self.company_id.id])],
                    'active': True,
                })
                _logger.info('Cuenta Portal de chofer creada: user_id=%s.', user.id)
        registrations = self.env['transcash.chofer'].sudo().search([('usuario_id', '=', user.id)])
        if not registrations:
            registrations = self.env['transcash.chofer'].sudo().create({
                'usuario_id': user.id, 'company_id': self.company_id.id,
                'activo': True, 'carga_autonoma': False,
                'empresa_transporte_id': transport.id if transport else False,
            })
        elif transport and not registrations.empresa_transporte_id:
            registrations.sudo().write({'empresa_transporte_id': transport.id})
        if not registrations.activo:
            return False, _('Registro de chofer desactivado; el usuario existente se conserva.')
        if not user.has_group('logistica_transcash.group_transcash_chofer'):
            # Asociar res.users a la guía para planificar, pero sin habilitar PWA:
            # sus endpoints verifican de forma independiente el grupo Chofer.
            return user, _('Cuenta Portal asignada a la guía. Falta activar el perfil Chofer Transcash desde Choferes y acceso móvil. Cambie la contraseña inicial.')
        return user, ''

    def _has_role_portal(self, partner, role):
        """Verifica acceso existente; no crea permisos ni cuentas nuevas."""
        self.ensure_one()
        if not partner:
            return False
        group = ('logistica_transcash.group_transcash_cliente' if role == 'recipient'
                 else 'logistica_transcash.group_transcash_transportista')
        directory = ('transcash.acceso.cliente' if role == 'recipient'
                     else 'transcash.acceso.proveedor')
        # Portal del contacto o de algún empleado/hijo de su compañía comercial.
        users = self.env['res.users'].sudo().search([
            ('partner_id', 'child_of', partner.commercial_partner_id.id),
            ('share', '=', True), ('active', '=', True),
        ], limit=200)
        for user in users:
            if not user.has_group('base.group_portal') or not user.has_group(group):
                continue
            access = self.env[directory].sudo().search([('usuario_id', '=', user.id)])
            if not access or any(a.activo and a.company_id.id == self.company_id.id for a in access):
                return True
        return False

    def _link_master_partners(self):
        self.ensure_one()
        # Serializa el alta de terceros por empresa durante esta transacción.
        # Evita que dos sincronizaciones simultáneas creen duplicados.
        self.env.cr.execute('SELECT id FROM res_company WHERE id = %s FOR UPDATE', (self.company_id.id,))
        notes = []
        transport_name = self.transport_name or (self.transport_id.name if self.transport_id else '')
        transport_tax = self.transport_tax_raw or (self.transport_id.ruc if self.transport_id else '')
        transport, message = self._resolve_transport_partner(transport_name, transport_tax)
        if message:
            notes.append(message)
        # Si el ERP no informa RUC, no borrar un vínculo ya confirmado
        # cuando la identificación por nombre sigue siendo inequívoca.
        if not transport and not transport_tax and self.transport_partner_id:
            previous = self.transport_partner_id
            if ' '.join((previous.name or '').upper().split()) == ' '.join(transport_name.upper().split()):
                transport = previous
                notes.append(_('Vínculo existente conservado; falta RUC en ERP.'))
        if transport and not self._has_role_portal(transport, 'transport'):
            notes.append(_('Transportista sin perfil Portal de proveedor habilitado en esta empresa.'))
        driver_tax = self.driver_id.identification if self.driver_id else ''
        driver, message = self._upsert_contact('driver', self.driver_id.name if self.driver_id else '',
                                                tax=driver_tax)
        if message:
            notes.append(message)
        user, message = self._resolve_driver_user(driver, transport)
        if message:
            notes.append(message)
        # El contacto del chofer SIEMPRE se guarda aunque no tenga usuario Portal.
        # No se crea res.users ni un registro transcash.chofer sin usuario,
        # pues v5.32 exige un usuario Portal explícitamente habilitado.
        sender = False
        if self.sender_id:
            sender_code = _clean(self.sender_id.external_code)
            sender_tax = sender_code if sender_code.isdigit() and len(sender_code) in (10, 13) else ''
            sender, message = self._upsert_contact('sender', self.sender_id.name,
                tax=sender_tax, code=sender_code, street=self.origin_address, company=True)
            if message:
                notes.append(message)
        else:
            notes.append(_('Sin remitente identificado en el ERP.'))
        recipient = False
        if self.recipient_id:
            code = self.recipient_id.external_code
            tax = self.recipient_tax_raw or (code if code.isdigit() and len(code) in (10, 13) else '')
            recipient, message = self._upsert_contact('recipient', self.recipient_id.name,
                tax=tax, code=code, street=self.destination_address)
            if message:
                notes.append(message)
            if recipient and not self._has_role_portal(recipient, 'recipient'):
                notes.append(_('Destinatario sin perfil Portal de cliente habilitado en esta empresa.'))
        else:
            notes.append(_('Sin código identificador de destinatario en el ERP.'))
        vals = {
            'transport_partner_id': transport.id if transport else False,
            'driver_partner_id': driver.id if driver else False,
            'driver_user_id': user.id if user else False,
            'sender_partner_id': sender.id if sender else False,
            'recipient_partner_id': recipient.id if recipient else False,
            'master_link_state': 'pending' if notes else 'complete',
            'master_link_note': '\n'.join(notes)[:4000] if notes else False,
        }
        self.sudo().write(vals)

    def _publish_one(self):
        # Se ejecuta también para guías ya importadas cuando se concilian manualmente.
        self.ensure_one()
        self._link_master_partners()
        return super()._publish_one()

    def action_reconcile_related_partners(self):
        user = self.env.user
        if user.share or not (self.env.su or user.has_group('transcash_guias_api.group_tc_sync_admin')
                              or user.has_group('logistica_transcash.group_logistica_manager')):
            raise AccessError(_('Solo la administración de Logística puede conciliar terceros.'))
        success = failed = 0
        for rec in self:
            if rec.company_id not in user.company_ids and not self.env.su:
                raise AccessError(_('No tiene acceso a la compañía de esta guía.'))
            try:
                with self.env.cr.savepoint():
                    rec.sudo()._publish_one()
                    success += 1
            except Exception:
                failed += 1
                _logger.exception('Conciliación fallida para guía ERP %s', rec.external_id)
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Conciliación de terceros'),
            'message': _('Revisadas: %s; errores: %s. Las pendientes se muestran en Vínculos con el portal.') % (success, failed),
            'type': 'warning' if failed else 'success', 'sticky': bool(failed),
        }}

    @api.model
    def action_reconcile_company(self):
        user = self.env.user
        if user.share or not (self.env.su or user.has_group('transcash_guias_api.group_tc_sync_admin')
                              or user.has_group('logistica_transcash.group_logistica_manager')):
            raise AccessError(_('Sin permiso para conciliar terceros.'))
        guides = self.search([('company_id', '=', self.env.company.id)])
        return guides.action_reconcile_related_partners()
