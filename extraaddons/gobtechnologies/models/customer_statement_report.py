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
]

class RepaymentPaymentLine(models.Model):
    _name = 'repayment.payment.line'
    _description = 'Repayment Payment Line'

    repayment_id = fields.Many2one('repayment', string='Repayment', ondelete='cascade', invisible=True)
    payment_date = fields.Date(string='Date of Payment', required=True)
    payment_mode = fields.Selection([
        ('cash', 'Cash'),
        ('momo', 'Mobile Money'),
        ('cheque', 'Cheque'),
        ('bank', 'Bank Transfer')
    ], string='Mode of Payment', required=True)
    payment_amount = fields.Float(string='Payment Amount', required=True)
    payment_date = fields.Date(string='Payment Date', required=True)
    is_payment_insufficient = fields.Boolean(
        string='Payment Insufficient',
        compute='_compute_is_payment_insufficient',
        store=True
    )
    payment_status = fields.Char(
        string='Status',
        compute='_compute_payment_status',
        store=True
    )

    # This field is needed for underpayment expected to pay field
    expected_amount = fields.Float(
        string='Expected Amount',
        related='repayment_id.expected_to_pay',
        store=True
    )



    # Check if payment is insufficient and change the payment amount color to red
    @api.depends('payment_amount', 'repayment_id.expected_to_pay')
    def _compute_is_payment_insufficient(self):
        for record in self:
            record.is_payment_insufficient = record.payment_amount < record.repayment_id.expected_to_pay

    @api.depends('payment_amount', 'repayment_id.expected_to_pay')
    def _compute_payment_status(self):
        for record in self:
            if record.payment_amount > record.repayment_id.expected_to_pay:
                record.payment_status = 'Overpaid'
                record.is_payment_insufficient = False
            elif record.payment_amount < record.repayment_id.expected_to_pay:
                record.payment_status = 'Underpaid'
                record.is_payment_insufficient = True
            else:
                record.payment_status = 'Fully Paid'
                record.is_payment_insufficient = False

    @api.model
    def create(self, vals):
        res = super(RepaymentPaymentLine, self).create(vals)
        # Check and update state after payment
        repayment = res.repayment_id
        if repayment.outstanding_loan <= 0:
            repayment.write({'state': 'paid'})
        return res

    def write(self, vals):
        res = super(RepaymentPaymentLine, self).write(vals)
        # Check and update state after payment
        repayment = self.repayment_id
        if repayment.outstanding_loan <= 0:
            repayment.write({'state': 'paid'})
        return res

    @api.model
    def get_payment_status_distribution(self):
        """Get the distribution of payment statuses"""
        domain = [('payment_date', '>=', fields.Date.today() - relativedelta(months=1))]
        fully_paid = self.search_count(domain + [('is_payment_insufficient', '=', False)])
        underpaid = self.search_count(domain + [('is_payment_insufficient', '=', True)])
        return {
            'fully_paid': fully_paid,
            'underpaid': underpaid
        }

    # For Dashboard Report
    @api.model
    def get_monthly_collections(self):
        """Get monthly collection trends"""
        start_date = fields.Date.today() - relativedelta(months=6)
        
        # Group by month and sum amounts
        self.env.cr.execute("""
            SELECT 
                date_trunc('month', payment_date) as month,
                SUM(payment_amount) as actual,
                SUM(expected_amount) as expected
            FROM repayment_payment_line
            WHERE payment_date >= %s
            GROUP BY date_trunc('month', payment_date)
            ORDER BY month
        """, (start_date,))
        
        results = self.env.cr.dictfetchall()
        return {
            'months': [r['month'].strftime('%B %Y') for r in results],
            'actual': [r['actual'] for r in results],
            'expected': [r['expected'] for r in results]
        }


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
    payment_lines = fields.One2many(
        'repayment.payment.line',  # Related model
        'repayment_id',  # Field in the related model pointing back to this model
        string='Payments',
    )
    plan = fields.Selection([
        ('30', '30 days'),
        ('60', '60 days'),
        ('90', '90 days'),
        ('120', '120 days'),
        ('cash', 'Cash')
    ], string='Plan', required=True)
    start_date = fields.Date(string='Start Date', required=True)
    selling_price= fields.Float(string='Selling Price', store=True)
    deposit = fields.Float(string='Deposit', required=True)
    repayment = fields.Float(string='Repayment Amount', compute='_compute_repayment', readonly=True, store=True)
    expected_to_pay = fields.Float(string='Expected to Pay', required=True)
    repayment_frequency = fields.Selection([
        ('1', 'Daily'),
        ('14', 'Weekly'),
        ('30', 'Monthly'),
        ('0', 'Cash')
    ], string='Repayment Frequency', required=True)
    repayment_date = fields.Date(
        string='Repayment Date',
        compute='_compute_repayment_date',
        store=True
    )
    end_date = fields.Date(string='End Date', required=True)
    duration_left = fields.Integer(string='Duration Left', compute='_compute_duration_left', store=True)
    due_date = fields.Date(string='Due Date', compute='_compute_due_date', store=True)
    reminder = fields.Char(string='Reminder', compute='_compute_reminder', store=True)
    total_paid = fields.Float(string='Total Paid', compute='_compute_total_paid', store=True)
    outstanding_loan = fields.Float(string='Outstanding Debt', compute='_compute_outstanding_loan', store=True)
    phone_no = fields.Char(string='Phone No', required=True)
    penalty = fields.Integer(string='Penalty')
    discount = fields.Integer(string='Discount')
    percentage_paid = fields.Float(string='Percentage Paid', compute='_compute_percentage_paid', store=True)
    paid_to_momo = fields.Float(string='Paid to Momo')
    guarantor_name = fields.Many2one('res.partner', string='Guarantor Name', required=True)
    guarantor_contact = fields.Char(string='Guarantor Contact', required=True)
    state = fields.Selection(
        selection=PAYMENT_STATE,
        string="Status",
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
    is_payment_missed = fields.Boolean(
        string='Payment Missed',
        compute='_compute_payment_missed',
        store=True
    )

    # Compute the repayment amount
    @api.depends('payment_lines.payment_amount')
    def _compute_repayment(self):
        for rec in self:
            rec.repayment = sum(rec.payment_lines.mapped('payment_amount'))

    # Set state to progress and generate a unique id for repayment when record is created
    @api.model
    def create(self, vals):
        vals['state'] = 'progress'
        if vals.get('unique_id', _('New')) == _('New'):
            vals['unique_id'] = self.env['ir.sequence'].next_by_code('repayment.sequence') or _('New')
        return super(Repayment, self).create(vals)

    # update state when record is updated
    def write(self, vals):
        if 'state' not in vals:  # Only override if state is not being explicitly changed
            vals['state'] = 'progress'
        return super(Repayment, self).write(vals)


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
                record.total_paid = 0.0

    # Computes the outstnding loan
    @api.depends('selling_price', 'total_paid', 'deposit')
    def _compute_outstanding_loan(self):
        for record in self:
            if record.selling_price and record.total_paid:
                record.outstanding_loan = record.selling_price - record.total_paid
            elif record.selling_price and record.deposit and not record.total_paid:
                record.outstanding_loan = record.selling_price - record.deposit
            else:
                record.total_paid = 0.0


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

    # Cancel Button
    def action_cancel(self):
        self.state = 'draft'
        return True

    # Computes the next repayment date
    @api.depends('start_date', 'repayment_frequency', 'payment_lines.payment_date')
    def _compute_repayment_date(self):
        for record in self:
            if not record.start_date or not record.repayment_frequency:
                record.repayment_date = False
                continue

            # Find the last payment date
            last_payment = record.payment_lines.sorted(lambda p: p.payment_date, reverse=True)[:1]
            base_date = last_payment.payment_date if last_payment else record.start_date

            # Calculate next repayment date based on frequency
            if record.repayment_frequency == '1':  # Daily
                record.repayment_date = base_date + timedelta(days=1)
            elif record.repayment_frequency == '14':  # Weekly
                record.repayment_date = base_date + timedelta(days=7)
            elif record.repayment_frequency == '30':  # Monthly
                record.repayment_date = base_date + timedelta(days=30)
            else:  # Cash
                record.repayment_date = base_date

    # Computes payment missed
    @api.depends('repayment_date', 'payment_lines.payment_date', 'payment_lines.payment_amount', 'expected_to_pay')
    def _compute_payment_missed(self):
        today = fields.Date.today()
        for record in self:
            if not record.repayment_date:
                record.is_payment_missed = False
                continue

            # Find payments made on the expected repayment date
            payments_on_date = record.payment_lines.filtered(
                lambda p: p.payment_date == record.repayment_date
            )
            
            # Calculate total payment amount for that date
            total_payment = sum(payments_on_date.mapped('payment_amount'))

            _logger.info(f"Payments found: {payments_on_date}")
            _logger.info(f"Repayment Date, Total payment: {record.repayment_date}, {total_payment}")
            
            if payments_on_date:
                if total_payment < record.expected_to_pay:
                    # Raise warning if payment amount is less than expected
                    message = _(
                        'Warning: Payment amount (%.2f) is less than expected amount (%.2f) for date %s'
                    ) % (total_payment, record.expected_to_pay, record.repayment_date)
                    
                    self.env['bus.bus']._sendone(
                        self.env.user.partner_id,
                        'warning',
                        {
                            'title': _('Insufficient Payment'),
                            'message': message,
                        }
                    )
                    record.is_payment_missed = True
                else:
                    record.is_payment_missed = False
            else:
                record.is_payment_missed = record.repayment_date < today

    def get_hubtel_credentials(self):
        credentials = self.env['res.config.settings'].get_hubtel_credentials()
        client_id = credentials.get('client_id')
        
        # Display using Odoo's notification system
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Hubtel Credentials',
                'message': f'Client ID: {client_id}',
                'sticky': True,
                'type': 'info',
                'position': 'bottom-right'
            }
        }

    @api.model
    def get_dashboard_data(self):
        """Get all dashboard data in one call"""
        PaymentLine = self.env['repayment.payment.line']
        
        # Payment Status Distribution
        payment_status = PaymentLine.get_payment_status_distribution()
        
        # Monthly Collections
        today = fields.Date.today()
        start_date = today - relativedelta(months=6)
        
        self.env.cr.execute("""
            SELECT 
                to_char(date_trunc('month', payment_date), 'Month') as month,
                SUM(payment_amount) as actual_amount,
                COUNT(*) as payment_count
            FROM repayment_payment_line
            WHERE payment_date >= %s
            GROUP BY date_trunc('month', payment_date)
            ORDER BY date_trunc('month', payment_date)
        """, (start_date,))
        
        collections_data = self.env.cr.dictfetchall()
        collections = {
            'months': [row['month'].strip() for row in collections_data],
            'actual': [row['actual_amount'] for row in collections_data],
            'expected': [row['actual_amount'] * 1.1 for row in collections_data]  # Example: expected is 10% more
        }
        
        # Payment Plan Distribution
        self.env.cr.execute("""
            SELECT repayment_frequency as plan, COUNT(*) as count
            FROM repayment
            WHERE state != 'cancel'
            GROUP BY repayment_frequency
        """)
        plan_distribution = {
            'labels': [],
            'data': []
        }
        for row in self.env.cr.dictfetchall():
            plan_distribution['labels'].append(f"{row['plan']} days")
            plan_distribution['data'].append(row['count'])

        # Outstanding Loans by Duration
        self.env.cr.execute("""
            SELECT 
                CASE 
                    WHEN duration_left <= 30 THEN '0-30 days'
                    WHEN duration_left <= 60 THEN '31-60 days'
                    WHEN duration_left <= 90 THEN '61-90 days'
                    ELSE '90+ days'
                END as duration_range,
                COUNT(*) as count,
                SUM(outstanding_loan) as total_outstanding
            FROM repayment
            WHERE state != 'cancel' AND outstanding_loan > 0
            GROUP BY 
                CASE 
                    WHEN duration_left <= 30 THEN '0-30 days'
                    WHEN duration_left <= 60 THEN '31-60 days'
                    WHEN duration_left <= 90 THEN '61-90 days'
                    ELSE '90+ days'
                END
            ORDER BY duration_range
        """)
        outstanding_by_duration = {
            'labels': [],
            'counts': [],
            'amounts': []
        }
        for row in self.env.cr.dictfetchall():
            outstanding_by_duration['labels'].append(row['duration_range'])
            outstanding_by_duration['counts'].append(row['count'])
            outstanding_by_duration['amounts'].append(row['total_outstanding'])

        # Payment Compliance Stats
        self.env.cr.execute("""
            SELECT 
                COUNT(*) as total_payments,
                SUM(CASE WHEN is_payment_insufficient THEN 1 ELSE 0 END) as underpaid_count,
                SUM(CASE WHEN payment_amount > expected_amount THEN 1 ELSE 0 END) as overpaid_count
            FROM repayment_payment_line
            WHERE payment_date >= CURRENT_DATE - INTERVAL '30 days'
        """)
        compliance_stats = self.env.cr.dictfetchone()

        return {
            'payment_status': payment_status,
            'collections': collections,
            'plan_distribution': plan_distribution,
            'outstanding_by_duration': outstanding_by_duration,
            'compliance_stats': compliance_stats or {
                'total_payments': 0,
                'underpaid_count': 0,
                'overpaid_count': 0
            }
        }

