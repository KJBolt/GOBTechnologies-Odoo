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

        # Redirect to Paypal checkout
        # html_content = """
        # <html>
        #     <head>
        #         <script>
        #             if (window.top !== window.self) {
        #                 // If inside an iframe, force a full-page redirect
        #                 window.top.location.href = "https://www.paypal.com/ncp/payment/VSU5DM3D24VJJ";
        #             } else {
        #                 // If not in an iframe, normal redirect
        #                 window.location.href = "https://www.paypal.com/ncp/payment/VSU5DM3D24VJJ";
        #             }
        #         </script>
        #     </head>
        #     <body></body>
        # </html>
        # """
        # return request.make_response(html_content, [('Content-Type', 'text/html')])

    # @http.route('/hubtel/payment/initiate', type='json', auth='public', methods=['POST'], csrf=False)
    # def initiate_payment(self, **kwargs):
    #     hubtel_url = "https://payproxyapi.hubtel.com/items/initiate"
        
    #     payload = {
    #         "totalAmount": kwargs.get("amount"),
    #         "description": kwargs.get("description"),
    #         "callbackUrl": request.httprequest.host_url + "hubtel/payment/callback",
    #         "returnUrl": request.httprequest.host_url + "shop/confirmation",
    #         "cancellationUrl": request.httprequest.host_url + "shop/payment",
    #         "merchantAccountNumber": "YOUR_HUBTEL_MERCHANT_ACCOUNT",
    #         "clientReference": kwargs.get("reference"),
    #         "customerPhoneNumber": kwargs.get("phone"),
    #     }

    #     headers = {
    #         "Authorization": "Basic YOUR_HUBTEL_API_KEY",
    #         "Content-Type": "application/json",
    #     }

    #     response = requests.post(hubtel_url, data=json.dumps(payload), headers=headers)
    #     res_data = response.json()

    #     return res_data

    # @http.route('/hubtel/payment/callback', type='http', auth='public', csrf=False)
    # def payment_callback(self, **kwargs):
    #     transaction_status = request.params.get("status")
    #     client_reference = request.params.get("clientReference")

    #     # Update payment status in Odoo
    #     sale_order = request.env['sale.order'].sudo().search([('name', '=', client_reference)], limit=1)
    #     if sale_order and transaction_status == 'Success':
    #         sale_order.sudo().action_confirm()
        
    #     return request.redirect('/shop/confirmation')

