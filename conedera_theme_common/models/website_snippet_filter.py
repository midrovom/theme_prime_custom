from odoo import _, api, fields, models
from odoo.http import request

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'
    
    def _filter_records_to_values(self, records, is_sample=False):
        res = super()._filter_records_to_values(records, is_sample)

        # Aplicar solo cuando el snippet está configurado para productos
        if self.model_name == 'product.template':
            for data in res:
                product = data['_record']

                # URL amigable del producto
                data['url'] = "/shop/product/%s" % request.env['ir.http']._slug(product)

                # Imagen por defecto si no tiene
                if not data.get('image_512'):
                    data['image_512'] = "/web/static/img/placeholder.png"

                # Obtener la marca asociada (campo product_brand_id si usas módulo de marcas)
                brand = getattr(product, 'product_brand_id', False)
                if brand:
                    data['brand'] = brand.name

                    # Traer todos los productos asociados a esa marca
                    brand_products = self.env['product.template'].search([
                        ('product_brand_id', '=', brand.id)
                    ])

                    # Convertir cada producto en un diccionario con toda su info
                    data['brand_products'] = []
                    for bp in brand_products:
                        data['brand_products'].append({
                            'name': bp.name,
                            'url': "/shop/product/%s" % request.env['ir.http']._slug(bp),
                            'price': bp.list_price,
                            'description': bp.description_sale or bp.description or '',
                            'image_512': bp.image_512 or "/web/static/img/placeholder.png",
                            'default_code': bp.default_code,
                            'product_type': bp.type,
                            'uom': bp.uom_id.name,
                            'categ': bp.categ_id.name,
                        })

        return res
    

    @api.model
    def _get_public_products(self, mode=None, **kwargs):
        dynamic_filter = self.env.context.get('dynamic_filter') 
        website = self.env['website'].get_current_website()

        # Dominio base para productos visibles en el website
        domain = [
            ('website_published', '=', True),   # Solo productos publicados
            ('website_id', 'in', [False, website.id]),  # Soporte multi-website
        ]

        # Traer productos ordenados por nombre
        products = self.env['product.template'].search(domain, order="name ASC")

        return dynamic_filter.with_context()._filter_records_to_values(products, is_sample=False)
