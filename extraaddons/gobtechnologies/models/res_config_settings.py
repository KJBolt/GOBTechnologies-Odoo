from odoo import fields, models, api
from ..utils.hash_utils import encrypt_text, decrypt_text
import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hubtel_client_id = fields.Char(
        string='Client ID',
        config_parameter='gobtechnologies.hubtel_client_id'
    )
    hubtel_client_secret = fields.Char(
        string='Client Secret',
        config_parameter='gobtechnologies.hubtel_client_secret'
    )
    hubtel_merchant_account = fields.Char(
        string='Merchant Account',
        config_parameter='gobtechnologies.hubtel_merchant_account'
    )


    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        
        # Decrypt values when getting them
        res.update({
            'hubtel_client_id': decrypt_text(params.get_param('gobtechnologies.hubtel_client_id', '')),
            'hubtel_client_secret': decrypt_text(params.get_param('gobtechnologies.hubtel_client_secret', '')),
            'hubtel_merchant_account': decrypt_text(params.get_param('gobtechnologies.hubtel_merchant_account', ''))
        })
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        
        # Encrypt values before saving
        self.env['ir.config_parameter'].sudo().set_param(
            'gobtechnologies.hubtel_client_id', 
            encrypt_text(self.hubtel_client_id or '')
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'gobtechnologies.hubtel_client_secret', 
            encrypt_text(self.hubtel_client_secret or '')
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'gobtechnologies.hubtel_merchant_account', 
            encrypt_text(self.hubtel_merchant_account or '')
        )

    @api.model
    def get_hubtel_credentials(self):
        """Get decrypted Hubtel credentials"""
        params = self.env['ir.config_parameter'].sudo()
        return {
            'client_id': decrypt_text(params.get_param('gobtechnologies.hubtel_client_id', '')),
            'client_secret': decrypt_text(params.get_param('gobtechnologies.hubtel_client_secret', '')),
            'merchant_account': decrypt_text(params.get_param('gobtechnologies.hubtel_merchant_account', ''))
        }

