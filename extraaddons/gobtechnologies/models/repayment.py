from odoo import api, fields, models, _
from datetime import timedelta
from dateutil.relativedelta import relativedelta 
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

PAYMENT_STATE = [
    ('draft', "Draft"),
    ('progress', "Payment in Progress"),
    ('paid', "Payment Completed"),
    ('cancel', "Cancelled"),
]

class RepaymentProductLine(models.Model):
    _name = 'repayment.product.line'
    _description = 'Repayment Product Line'

    product_id = fields.Many2one(
        'product.product', 
        string='Product', 
        required=True
    )
    amount = fields.Integer(
        string='Amount', 
        required=True, 
        default=1
    )
    price = fields.Float(
        string='Price', 
        compute='_compute_price',
        store=True
    )
    repayment_id = fields.Many2one(
        'repayment', 
        string='Repayment', 
        ondelete='cascade'
    )

    @api.depends('amount')
    def _compute_price(self):
        for record in self:
            if record.amount and record.product_id:
                record.price = record.amount * record.product_id.lst_price
            else:
                record.price = 0.0

    @api.model
    def _default_repayment_id(self):
        return self.env.context.get('default_repayment_id')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price = self.product_id.lst_price



class Repayment(models.Model):
    _name = 'repayment'
    _description = 'Repayment'

    unique_id = fields.Char(
        string="Reference",
        required=True, copy=False, readonly=True, index=True,
        default=lambda self: _('New')
    )
    customer_name = fields.Many2one('res.partner', string='Customer Name', required=True)
    gps_location = fields.Char(string='GPS Location', required=True)
    product_lines = fields.One2many(
        'repayment.product.line',  # Related model
        'repayment_id',  # Field in the related model pointing back to this model
        string='Products',
    )
    # product = fields.Many2one('product.product', string='Product', required=True)
    plan = fields.Selection([
        ('30', '30 days'),
        ('60', '60 days'),
        ('90', '90 days'),
        ('120', '120 days'),
        ('cash', 'Cash')
    ], string='Plan', required=True)
    start_date = fields.Date(string='Start Date', required=True)
    selling_price= fields.Float(string='Selling Price', compute='_compute_selling_price', store=True)
    deposit = fields.Float(string='Deposit', required=True)
    repayment = fields.Float(string='Repayment Amount', required=True)
    expected_to_pay = fields.Float(string='Expected to Pay', required=True)
    repayment_frequency = fields.Selection([
        ('1', 'Daily'),
        ('14', 'Weekly'),
        ('30', 'Monthly'),
        ('0', 'Cash')
    ], string='Repayment Frequency', required=True)
    repayment_date = fields.Date(string='Repayment Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    duration_left = fields.Integer(string='Duration Left', compute='_compute_duration_left', store=True)
    due_date = fields.Date(string='Due Date', compute='_compute_due_date', store=True)
    reminder = fields.Char(string='Reminder', compute='_compute_reminder', store=True)
    total_paid = fields.Float(string='Total Paid', compute='_compute_total_paid', store=True)
    outstanding_loan = fields.Float(string='Outstanding Loan', compute='_compute_outstanding_loan', store=True)
    phone_no = fields.Char(string='Phone No', required=True)
    penalty_discount = fields.Integer(string='Penalty / Discount', required=True)
    percentage_paid = fields.Float(string='Percentage Paid', compute='_compute_percentage_paid', store=True)
    paid_to_momo = fields.Float(string='Paid to Momo', required=True)
    guarantor_name = fields.Many2one('res.partner', string='Guarantor Name', required=True)
    guarantor_contact = fields.Char(string='Guarantor Contact', required=True)
    state = fields.Selection(
        selection=PAYMENT_STATE,
        string="Status",
        readonly=True, copy=False, index=True,
        tracking=3,
        default='draft')
    total_price = fields.Float(
        string='Total Price', 
        compute='_compute_total_price', 
        store=True
    )
    currency_id = fields.Many2one(
        'res.currency', 
        string='Currency', 
        default=lambda self: self.env.company.currency_id.id
    )

    # Set state to progress and generate a unique id for repayment when record is created
    @api.model
    def create(self, vals):
        vals['state'] = 'progress'
        if vals.get('unique_id', _('New')) == _('New'):
            vals['unique_id'] = self.env['ir.sequence'].next_by_code('repayment.sequence') or _('New')
        return super(Repayment, self).create(vals)


    # Ensure the product_lines field is not empty
    @api.constrains('product_lines')
    def _check_product_lines(self):
        for record in self:
            if not record.product_lines:
                raise ValidationError("You must add at least one product before proceeding.")

    # Update the total price and selling price upon update
    @api.depends('product_lines.price', 'product_lines.amount')
    def _compute_total_price(self):
        for record in self:
            record.total_price = sum(line.price * line.amount for line in record.product_lines)

    @api.depends('product_lines.price', 'product_lines.amount')
    def _compute_selling_price(self):
        for record in self:
            record.selling_price = sum(line.price * line.amount for line in record.product_lines)

    # Computes the duration left
    @api.depends('repayment_date', 'end_date')
    def _compute_duration_left(self):
        for record in self:
            if record.repayment_date and record.end_date:
                duration = record.end_date - record.repayment_date
                record.duration_left = duration.days
            else:
                record.duration_left = 0

    # Computes the due date
    @api.depends('repayment_date', 'repayment_frequency')
    def _compute_due_date(self):
        for record in self:
            if record.repayment_date and record.repayment_frequency:
                # Convert repayment_frequency to an integer if needed
                freq = int(record.repayment_frequency)

                if freq == 1:
                    due_date = record.repayment_date + timedelta(days=1)
                elif freq == 14:
                    due_date = record.repayment_date + timedelta(weeks=2)
                elif freq == 30:
                    due_date = record.repayment_date + relativedelta(months=1)
                elif freq == 0:
                    due_date = record.repayment_date
                else:
                    due_date = False  # Fallback in case of an invalid value

                record.due_date = due_date
            else:
                record.due_date = False 

    # Computes the reminder
    @api.depends('due_date')
    def _compute_reminder(self):
        today = fields.Date.today()
        for record in self:
            if today and today >= record.due_date:
                record.reminder = 'Due'
            else:
                record.reminder = 'Not Due'

    # Computes the total paid
    @api.depends('deposit', 'repayment')
    def _compute_total_paid(self):
        for record in self:
            if record.deposit and record.repayment:
                record.total_paid = record.deposit + record.repayment
            else:
                record.total_paid = 0

    # Computes the outstnding loan
    @api.depends('selling_price', 'total_paid')
    def _compute_outstanding_loan(self):
        for record in self:
            if record.selling_price and record.total_paid:
                record.outstanding_loan = record.selling_price - record.total_paid
            else:
                record.total_paid = 0

    # computes the percentage paid
    @api.depends('selling_price', 'total_paid')
    def _compute_percentage_paid(self):
        for record in self:
            if record.selling_price and record.total_paid:
                record.percentage_paid = (record.total_paid / record.selling_price) * 100
            else:
                record.percentage_paid = 0


    # Send Message to Customer
    def action_button_method(self):
        # Your method logic here
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Sms sent to {self.customer_name.name}',
                'sticky': False,
                'type': 'success',  # Can also use 'warning', 'danger', etc.
                'position': 'bottom-right'
            }
        }

    # Confirm Payment
    def action_confirm_payment(self):
        self.state = 'paid'
        return True
