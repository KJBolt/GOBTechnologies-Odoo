from odoo import models, fields, api
import logging

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
    payee_phone_no = fields.Char(string="Payee Phone No", required=False)
    payment_detail_id = fields.Char(string="Payment Detail Id", required=False)
    response_code = fields.Char(string="Response Code", required=False)
    payment_date = fields.Date(string="Payment Date", required=False)

    @api.model
    def create(self, vals):
        record = super(PaymentNotifications, self).create(vals)
        if 'payee_phone_no' in vals:
            record.process_payment()
        return record



    def process_payment(self):
        _logger.info("Computing Payment")

        repayment = self.env['repayment'].search([('phone_no', '=', self.payee_phone_no)], limit=1)

        if not repayment:
            _logger.info("No customer found with the provided phone number")

        # Check if payment line already exists for this date
        existing_line = self.env['repayment.payment.line'].search([
            ('repayment_id', '=', repayment.id),
            ('payment_date', '=', self.payment_date)
        ], limit=1)

        if not existing_line:
            repayment.payment_lines.create({
                'payment_date': self.payment_date,
                'payment_mode': 'momo',
                'payment_amount': self.amount_paid,
                'repayment_id': repayment.id
            })
            _logger.info(f"Payment line created for {self.payment_date}")
        else:
            _logger.info(f"Payment line for {self.payment_date} already exists, skipping creation.")

        return True