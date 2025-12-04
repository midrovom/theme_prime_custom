class WebsiteSaleCategories(http.Controller):

    @http.route(['/website_sale/get_categories'], type='json', auth='public', website=True)
    def get_dynamic_snippet_categories(self, filter_id=None, limit=None, search_domain=None, with_sample=False):
        """
        Returns categories for dynamic snippet based on filter and search domain
        """
        domain = request.website.sale_get_order() and request.website.website_domain() or []
        
        if search_domain:
            domain += search_domain
        
        # Always show only published categories
        domain += [('website_published', '=', True)]
        
        Category = request.env['product.public.category']
        
        if filter_id:
            filter_sudo = request.env['website.snippet.filter'].sudo().browse(int(filter_id))
            if filter_sudo.exists():
                domain += filter_sudo._get_eval_domain()
        
        categories = Category.search(domain, limit=limit or 16)
        
        # Prepare data
        category_data = []
        for category in categories:
            data = {
                '_record': category,
                'display_name': category.display_name,
                'image_512': category.image_512 and f'/web/image/product.public.category/{category.id}/image_512' or '/web/static/src/img/placeholder.png',
                'image_1920': category.image_1920 and f'/web/image/product.public.category/{category.id}/image_1920' or '/web/static/src/img/placeholder.png',
                'url': f'/shop/category/{category.id}',
            }
            category_data.append(data)
        
        return {
            'records': category_data,
            'is_sample': with_sample,
        }