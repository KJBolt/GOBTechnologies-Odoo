from odoo import http
from odoo.http import request
import json
import requests
from werkzeug.wrappers import Response

class HubtelPaymentController(http.Controller):

    @http.route('/shop/hubtel_payment', type='http', auth='public', methods=['POST'], website=True, csrf=False)
    def hubtel_payment(self, **kwargs):
        order_id = kwargs.get("order_id")
        sale_order = request.env['sale.order'].sudo().browse(int(order_id))
        if not sale_order.exists():
            return http.Response('Order not found', content_type="text/plain")
        order_total = sale_order.amount_total
        return http.Response(str(order_total), content_type="text/plain")


