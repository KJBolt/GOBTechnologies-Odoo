from odoo import http
from odoo.http import request
import json

class ProductDetailsController(http.Controller):
    @http.route('/shop/product/<int:product_id>', type='http', auth='public', methods=['GET'], website=True, csrf=False)
    def get_product_details(self, product_id, **kwargs):
        """
        Display product details for a specific product
        :param product_id: ID of the product to display
        """
        # Search for the product by ID
        product = request.env['product.template'].sudo().search([
            ('id', '=', product_id),
            ('sale_ok', '=', True),
            ('active', '=', True)
        ], limit=1)
        
        # If product not found, redirect to products page or show 404
        if not product:
            return request.render('website.404')
        
        # Prepare values for the template
        values = {
            'product': product,
        }
        
        return request.render('gobtechnologies.product_details_template', values)   
                
        
    