from odoo import models, fields, api
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class InvoiceWebhook(models.Model):
    _name = 'payment.notifications'
    _description = 'Payment Notifications'

    status = fields.Char(string="Status", required=False)
    amount_paid = fields.Float(string="Amount Paid", required=False)
    invoice_id = fields.Char(string="Invoice Id", required=False)
    receipt_no = fields.Char(string="Receipt No", required=False)
    description = fields.Char(string="Description", required=False)
    payment_method = fields.Char(string="Payment Method", required=False)
    payment_channel = fields.Char(string="Payment Channel", required=False)
    payee_phone_no = fields.Char(string="Payee Phone No", compute="_compute_phone_no", store=True)
    payment_detail_id = fields.Char(string="Payment Detail Id", required=False)
    response_code = fields.Char(string="Response Code", required=False)
    payment_date = fields.Date(string="Payment Date", required=False)

    # @api.model
    # def create(self, vals):
    #     record = super(InvoiceWebhook, self).create(vals)
    #     if 'payee_phone_no' in vals:
    #         record.process_payment()
    #     return record

    @api.depends('invoice_id')
    def _compute_phone_no(self):
        _logger.info("Computing Phone No")
        for record in self:
            if record.payee_phone_no:
                phone_no = record.payee_phone_no

                if phone_no.startswith('233'):
                    phone_no = '0' + phone_no[3:]

                record.payee_phone_no = phone_no

                # Call process payment method
                self.process_payment()    

                _logger.info(f"Extracted Phone No: {record.payee_phone_no}")


    def process_payment(self):
        _logger.info(f"Computing Payment")
        for record in self:
            repayment = self.env['repayment'].search([('phone_no', '=', record.payee_phone_no)], limit=1)
            if not repayment:
                raise UserError("No customer found with the provided phone number")
            existing_line = self.env['repayment.payment.line'].search([
                ('repayment_id', '=', repayment.id),
                ('payment_date', '=', record.payment_date)
            ], limit=1)
            if existing_line:
                repayment.payment_lines.create({
                    'payment_date': record.payment_date,
                    'payment_mode': 'momo',
                    'payment_amount': record.amount_paid,
                    'repayment_id': repayment.id
                })
                _logger.info(f"Payment line created for {record.payment_date}")