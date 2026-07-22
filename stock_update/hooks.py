from odoo import api, SUPERUSER_ID

def post_init_hook(env):
    agotado_ribbon = env['product.ribbon'].browse(2)  # tu cinta "Agotado"

    products = env['product.template'].search([])
    for product in products:
        if product.qty_available <= 0:
            product.allow_out_of_stock_order = False
            if agotado_ribbon:
                product.website_ribbon_id = agotado_ribbon.id
        else:
            product.allow_out_of_stock_order = True
            product.website_ribbon_id = False
