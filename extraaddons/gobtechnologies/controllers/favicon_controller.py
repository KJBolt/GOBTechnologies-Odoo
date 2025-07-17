from odoo import http
from odoo.http import request
import os

class FaviconController(http.Controller):
    @http.route(['/web/favicon.ico', '/favicon.ico'], type='http', auth="public", website=True)
    def favicon(self, **kw):
        return request.env['ir.http']._content_manifest('gobtechnologies', 'static/description/splitpay.png')