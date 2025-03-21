from odoo import api, fields, models

class HubtelWebhook(models.Model):
    _name = 'hubtel.webhook'
    _description = 'Hubtel Webhook'

    payload_data = fields.Text(string='Payload', required=True)
