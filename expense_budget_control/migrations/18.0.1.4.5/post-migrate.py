# -*- coding: utf-8 -*-
"""Remove legacy implicit Consulta membership from users with a specific role.

Prior to 1.4.5, Registro/Aprobador/Administrador inherited Consulta, so its
menus could not be hidden. A hidden technical reading group now supplies the
same model read access independently of menu visibility.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ref = env.ref
    consultation = ref('expense_budget_control.group_expense_budget_user', raise_if_not_found=False)
    if not consultation:
        return
    ids = []
    for name in ('group_expense_budget_registrar', 'group_expense_budget_approver', 'group_expense_budget_manager'):
        g = ref('expense_budget_control.' + name, raise_if_not_found=False)
        if g:
            ids.append(g.id)
    if ids:
        # Remove the membership only from users with an operational role.
        # Pure consultation users retain the Consulta group and its menus.
        cr.execute("""
            DELETE FROM res_groups_users_rel AS u
            WHERE u.gid = %s AND EXISTS (
                SELECT 1 FROM res_groups_users_rel AS roles
                WHERE roles.uid = u.uid AND roles.gid = ANY(%s)
            )
        """, (consultation.id, ids))
