from odoo import api, fields, models, _
from datetime import timedelta
from dateutil.relativedelta import relativedelta 
import logging
from odoo.exceptions import ValidationError, UserError
import requests
import json

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
    # payment_date = fields.Date(string='Payment Date', required=True)
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

        # Only mark as paid if total_paid matches or exceeds selling_price
        if repayment.total_paid >= repayment.selling_price:
            repayment.write({'state': 'paid'})
        else:
            repayment.write({'state': 'progress'})
        
        res.testpayment(vals)
        return res
        

    def write(self, vals):
        res = super(RepaymentPaymentLine, self).write(vals)
        # Check and update state after payment
        repayment = self.repayment_id
        _logger.info(f"Oustanding loan when updating: {repayment.outstanding_loan}")
        
        # Only mark as paid if total_paid matches or exceeds selling_price
        if repayment.total_paid >= repayment.selling_price:
            repayment.write({'state': 'paid'})
        else:
            repayment.write({'state': 'progress'})

        return res

    def testpayment(self, vals):
        # Get current payment date and amount
        current_payment_date = fields.Date.from_string(vals.get('payment_date'))
        current_payment_amount = vals.get('payment_amount')
        previous_payment_date = current_payment_date - timedelta(days=1)

        _logger.info(f"Previous payment date: {previous_payment_date}")
        _logger.info(f"Current payment amount: {current_payment_amount}")
        _logger.info(f"Current payment date: {current_payment_date}")

        # Get all payments for the previous date
        previous_date_payments = self.repayment_id.payment_lines.filtered(
            lambda p: p.payment_date == previous_payment_date
        )
        
        previous_payment_total = sum(previous_date_payments.mapped('payment_amount'))

        # Check if previous payment was insufficient
        if previous_date_payments and previous_payment_total < self.repayment_id.expected_to_pay:
            shortage = self.repayment_id.expected_to_pay - previous_payment_total
            
            # If current payment can cover the shortage
            if current_payment_amount >= shortage:
                # Amount to be used from current payment
                amount_to_previous = shortage
                # Remaining amount for current payment
                remaining_current = current_payment_amount - shortage
                
                if previous_date_payments:
                    # Update existing previous payment
                    previous_date_payments[0].write({
                        'payment_amount': previous_payment_total + amount_to_previous
                    })
                else:
                    # Create new payment record for previous date
                    self.env['repayment.payment.line'].create({
                        'payment_date': previous_payment_date,
                        'payment_amount': amount_to_previous,
                        'repayment_id': self.repayment_id.id,
                        'payment_mode': 'momo'  
                    })

                # Update the current payment with remaining amount
                self.write({
                    'payment_amount': remaining_current
                })

                _logger.info(f"Previous payment was insufficient. Added {amount_to_previous} from current payment")
                _logger.info(f"Previous payment updated to: {previous_payment_total + amount_to_previous}")
                _logger.info(f"Current payment updated to: {remaining_current}")
            else:
                _logger.info("Current payment insufficient to cover previous payment shortage")


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
    client_reference = fields.Char(string='Client Reference')
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
        ('7', 'Weekly'),
        ('30', 'Monthly'),
        ('0', 'Cash')
    ], string='Repayment Frequency', required=True)
    repayment_date = fields.Date(
        string='Repayment Date',
        compute='_compute_repayment_date',
        store=True
    )
    last_repayment_date = fields.Date(string='Last Repayment Date', store=True)
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
    overdue_status = fields.Boolean(string="Overdue Status", compute='_compute_overdue_status', store=True)
    overdue_amount = fields.Float(string='Overdue Amount', compute='_compute_overdue_amount', store=True)
    payment_status = fields.Selection([
        ('on_track', 'On Track'),
        ('overdue', 'Overdue'),
        ('insufficient', 'Insufficient Payment')
    ], string='Payment Status', compute='_compute_payment_status', store=True)
    penalty_ids = fields.One2many('repayment.penalty', 'repayment_id', string='Penalties')
    total_penalties = fields.Float(string='Total Penalties', compute='_compute_total_penalties', store=True)

    @api.depends('penalty_ids.penalty_amount')
    def _compute_total_penalties(self):
        for record in self:
            record.total_penalties = sum(record.penalty_ids.mapped('penalty_amount'))

    # Compute the repayment amount
    @api.depends('payment_lines.payment_amount')
    def _compute_repayment(self):
        for rec in self:
            rec.repayment = sum(rec.payment_lines.mapped('payment_amount'))

    # Set state to progress and generate a unique id for repayment when record is created
    @api.model
    def create(self, vals):
        if vals.get('unique_id', _('New')) == _('New'):
            vals['unique_id'] = self.env['ir.sequence'].next_by_code('repayment.sequence') or _('New')
        
        vals['state'] = 'progress'
        res = super(Repayment, self).create(vals)
        
        # Send sms to user upon account creation
        try:
            # Get customer name from res.partner
            customer = self.env['res.partner'].browse(vals.get('customer_name'))
            customer_name = customer.name if customer else "Customer"

            # Prepare SMS message
            sms_message = f"Dear {customer_name}, your account has been successfully created with GOB Technologies."

            # Send SMS
            if res.phone_no:
                self._send_hubtel_sms(res.phone_no, sms_message, customer_name)
            
        except Exception as e:
            _logger.error(f"Error sending welcome SMS: {str(e)}")

        return res

    # update state when record is updated
    def write(self, vals):
        res = super(Repayment, self).write(vals)
        if 'state' not in vals:  # Only check payment status if state is not being explicitly changed
            if self.total_paid >= self.selling_price:
                vals['state'] = 'paid'
            else:
                vals['state'] = 'progress'
        
        return res


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

    # Show overdue badge if todays date is greater than end date
    @api.depends('repayment_date', 'end_date', 'total_paid', 'selling_price')
    def _compute_overdue_status(self):
        for record in self:
            today = fields.Date.today()
            tomorrow = today + timedelta(days=1)
            
            # First check if record is fully paid
            if record.total_paid >= record.selling_price:
                record.overdue_status = False
                continue
                
            # Set to False if end_date is not set
            if not record.end_date:
                record.overdue_status = False
                continue
                
            # Only check overdue status if we have an end_date and not fully paid
            record.overdue_status = tomorrow > record.end_date
            _logger.info(f"Overdue Status: {record.overdue_status}")



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
            if not record.due_date:
                record.reminder = 'Not Due'
                continue
                
            if today >= record.due_date:
                record.reminder = 'Due'
            else:
                record.reminder = 'Not Due'

    # Computes the total paid
    @api.depends('deposit', 'repayment')
    def _compute_total_paid(self):
        for record in self:
            if record.deposit and record.repayment:
                record.total_paid = record.deposit + record.repayment
            elif not record.repayment and record.deposit:
                record.total_paid = record.deposit
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
    @api.depends('start_date', 'repayment_frequency', 'payment_lines.payment_date', 'expected_to_pay')
    def _compute_repayment_date(self):
        for record in self:
            # Default to False
            record.repayment_date = False
            
            # Basic validation
            if not record.start_date or not record.repayment_frequency:
                continue

            try:
                freq = int(record.repayment_frequency)
            except (ValueError, TypeError):
                continue

            # If no payment lines, calculate from start date
            if not record.payment_lines:
                if freq == 1:
                    record.repayment_date = record.start_date + timedelta(days=1)
                elif freq == 7:
                    record.repayment_date = record.start_date + timedelta(weeks=1)
                elif freq == 30:
                    record.repayment_date = record.start_date + relativedelta(months=1)
                else:
                    record.repayment_date = record.start_date
                continue

            # Get payments sorted by date
            payment_lines_sorted = record.payment_lines.sorted(lambda p: p.payment_date, reverse=True)
            if not payment_lines_sorted:
                record.repayment_date = record.start_date
                continue

            current_payment = payment_lines_sorted[0]
            current_payment_date = current_payment.payment_date
            current_payment_amount = current_payment.payment_amount

            # Calculate next repayment date based on payment amount
            if current_payment_amount >= record.expected_to_pay:
                full_payments = int(current_payment_amount // record.expected_to_pay)
                if freq == 1:
                    record.repayment_date = current_payment_date + timedelta(days=full_payments)
                elif freq == 7:
                    record.repayment_date = current_payment_date + timedelta(weeks=full_payments)
                elif freq == 30:
                    record.repayment_date = current_payment_date + relativedelta(months=full_payments)
            else:
                # If payment is insufficient, keep current repayment date
                record.repayment_date = current_payment_date


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
                    record.is_payment_missed = True
                else:
                    record.is_payment_missed = False
            else:
                record.is_payment_missed = record.repayment_date < today


    # Send SMS to customer
    def _send_hubtel_sms(self, phone, sms_message, customer_name):
        """Helper method to send SMS via Hubtel API using GET request"""
        try:
            # Get Hubtel credentials from settings
            settings = self.env['res.config.settings'].get_hubtel_credentials()
            client_id = settings.get('client_id')
            client_secret = settings.get('client_secret')
            merchant_account = settings.get('merchant_account')
            
            if not all([client_id, client_secret, merchant_account]):
                _logger.error("Missing Hubtel credentials")
                return False

            # Construct URL directly
            url = f"https://sms.hubtel.com/v1/messages/send?clientid={client_id}&clientsecret={client_secret}&from={merchant_account}&to={phone}&content={sms_message}"
            
            # Log the URL (with sensitive data masked)
            _logger.info(f"Making request to: {url}")
            
            # Make GET request
            response = requests.get(url, timeout=30)
            
            _logger.info(f"SMS API Response Status: {response.status_code}")
            _logger.info(f"SMS API Response: {response.text}")
            
            if response.status_code in [200, 201]:
                _logger.info(f"SMS sent successfully to {phone}")
                
                # Send notification to user
                channel = f"hubtel_notification_{self.env.user.partner_id.id}"
                notification_type = 'notify_user'
                message = {'msg': f'Account creation sms sent to {customer_name}'}
                self.env['bus.bus']._sendone(channel, notification_type, message)
                return True
            else:
                _logger.error(f"Failed to send SMS. Status: {response.status_code}, Response: {response.text}")
                return False
            
        except Exception as e:
            _logger.error(f"Failed to send SMS: {str(e)}")
            return False


    # Send repayment reminders
    @api.model
    def _send_repayment_reminders(self):
        today = fields.Date.today()
        tomorrow = today + timedelta(days=1)
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)
        three_days_ago = today - timedelta(days=3)
        
        # Find all active repayments
        repayments = self.search([
            ('state', '=', 'progress'),
            ('outstanding_loan', '>', 0)
        ])
        
        for repayment in repayments:
            try:
                # Skip if no repayment date
                if not repayment.repayment_date:
                    continue
                
                # Check for upcoming payments and overdue payments
                should_remind = False
                is_overdue = False
                should_send_penalty_reminder = False
                should_charge_penalty = False
                
                if repayment.repayment_frequency == '1':  # Daily
                    should_remind = tomorrow == repayment.repayment_date
                    is_overdue = yesterday == repayment.repayment_date
                    should_send_penalty_reminder = two_days_ago == repayment.repayment_date
                    should_charge_penalty = three_days_ago == repayment.repayment_date
                elif repayment.repayment_frequency == '14':  # Weekly
                    days_until_payment = (repayment.repayment_date - tomorrow).days
                    days_since_payment = (today - repayment.repayment_date).days
                    should_remind = days_until_payment == 0
                    is_overdue = days_since_payment == 1
                    should_send_penalty_reminder = days_since_payment == 2
                    should_charge_penalty = days_since_payment == 3
                elif repayment.repayment_frequency == '30':  # Monthly
                    days_until_payment = (repayment.repayment_date - tomorrow).days
                    days_since_payment = (today - repayment.repayment_date).days
                    should_remind = days_until_payment == 0
                    is_overdue = days_since_payment == 1
                    should_send_penalty_reminder = days_since_payment == 2
                    should_charge_penalty = days_since_payment == 3
                elif repayment.repayment_frequency == '0':  # Cash
                    continue
                
                # Send reminder for upcoming payment
                if should_remind and repayment.outstanding_loan > 0:
                    reminder_message = (
                        f"Dear {repayment.customer_name.name}, "
                        f"this is a reminder that your payment of GHS {repayment.expected_to_pay} "
                        f"is due tomorrow {tomorrow.strftime('%d-%m-%Y')}. "
                        f"Kindly dial *713*7678# to pay now to avoid any penalties."
                        f"Thank you for choosing GOB Technologies."
                    )
                    
                    if repayment.phone_no:
                        self._send_hubtel_sms(repayment.phone_no, reminder_message, repayment.customer_name.name)
                        
                    _logger.info(
                        f"Sent reminder to {repayment.customer_name.name} "
                        f"for {repayment.repayment_frequency} payment due on {tomorrow}"
                    )
                
                # Check if payment was made yesterday or today
                if is_overdue and repayment.outstanding_loan > 0:
                    # Find payments made on the due date (yesterday) or today
                    payments = repayment.payment_lines.filtered(
                        lambda p: p.payment_date in [yesterday, today]
                    )
                    
                    # Calculate total payment amount
                    total_payment = sum(payments.mapped('payment_amount'))
                    
                    # Only send overdue notice if no payment or insufficient payment
                    if not payments or total_payment < repayment.expected_to_pay:
                        payment_status = "not made" if not payments else "insufficient"
                        overdue_message = (
                            f"Dear {repayment.customer_name.name}, "
                            f"your payment of GHS {repayment.expected_to_pay} was due yesterday"
                            f"Kindly dial *713*7678# to pay now to avoid any penalties."
                            f"Thank you for choosing GOB Technologies."
                        )
                        
                        if repayment.phone_no:
                            self._send_hubtel_sms(repayment.phone_no, overdue_message, repayment.customer_name.name)
                            
                        _logger.info(
                            f"Sent overdue notice to {repayment.customer_name.name} "
                            f"for {repayment.repayment_frequency} payment due on {yesterday}. "
                            f"Payment status: {payment_status}"
                        )
                    else:
                        _logger.info(
                            f"No overdue notice sent to {repayment.customer_name.name} "
                            f"as payment was received (Total: {total_payment})"
                        )

                # Check for penalty reminder (2 days after due date)
                if should_send_penalty_reminder and repayment.outstanding_loan > 0:
                    # Check if payment was made in the last 2 days
                    recent_payments = repayment.payment_lines.filtered(
                        lambda p: p.payment_date >= two_days_ago
                    )
                    total_recent_payment = sum(recent_payments.mapped('payment_amount'))
                    
                    if not recent_payments or total_recent_payment < repayment.expected_to_pay:
                        penalty_reminder_message = (
                            f"Dear {repayment.customer_name.name}, "
                            f"your payment of GHS {repayment.expected_to_pay} is still pending. "
                            f"Please note that a penalty fee of GHS 10 will be charged tomorrow "
                            f"if payment is not made today. "
                            f"Kindly dial *713*7678# to pay now. "
                            f"Thank you for choosing GOB Technologies."
                        )
                        
                        if repayment.phone_no:
                            self._send_hubtel_sms(repayment.phone_no, penalty_reminder_message, repayment.customer_name.name)
                        
                        _logger.info(
                            f"Sent penalty warning to {repayment.customer_name.name} "
                            f"for payment due on {two_days_ago}"
                        )

                # Check for penalty charge (3 days after due date)
                if should_charge_penalty and repayment.outstanding_loan > 0:
                    # Check if payment was made in the last 3 days
                    recent_payments = repayment.payment_lines.filtered(
                        lambda p: p.payment_date >= three_days_ago
                    )
                    total_recent_payment = sum(recent_payments.mapped('payment_amount'))
                    
                    if not recent_payments or total_recent_payment < repayment.expected_to_pay:
                        # Add penalty charge
                        penalty_amount = 10.0  # GHS 10
                        
                        # Create penalty charge record
                        self.env['repayment.penalty'].create({
                            'repayment_id': repayment.id,
                            'penalty_date': today,
                            'penalty_amount': penalty_amount,
                            'reason': 'Late payment penalty'
                        })
                        
                        
                        # Update outstanding loan amount to include penalty
                        repayment.write({
                            'outstanding_loan': repayment.outstanding_loan + penalty_amount,
                            'penalty': penalty_amount
                        })
                        
                        penalty_charge_message = (
                            f"Dear {repayment.customer_name.name}, "
                            f"a penalty fee of GHS {penalty_amount} has been charged to your account "
                            f"due to delayed payment. Your new outstanding balance is "
                            f"GHS {repayment.outstanding_loan}. "
                            f"Kindly dial *713*7678# to pay now. "
                            f"Thank you for choosing GOB Technologies."
                        )
                        
                        if repayment.phone_no:
                            self._send_hubtel_sms(repayment.phone_no, penalty_charge_message, repayment.customer_name.name)
                        
                        _logger.info(
                            f"Applied penalty charge to {repayment.customer_name.name} "
                            f"for payment due on {three_days_ago}"
                        )

            except Exception as e:
                _logger.error(f"Failed to process reminders for {repayment.customer_name.name}: {str(e)}")
                raise ValidationError(f"Failed to process reminders for {repayment.customer_name.name}: {str(e)}")


    # Compute payment status
    @api.depends('repayment_date', 'payment_lines.payment_date', 'payment_lines.payment_amount', 'expected_to_pay')
    def _compute_payment_status(self):
        today = fields.Date.today()
        for record in self:
            if not record.repayment_date:
                record.payment_status = 'on_track'
                continue

            # Get payments in current period
            current_period_start = record.start_date
            current_period_end = record.repayment_date
            
            current_period_payments = record.payment_lines.filtered(
                lambda p: current_period_start <= p.payment_date <= current_period_end
            )
            total_paid_in_period = sum(current_period_payments.mapped('payment_amount'))

            if today > record.repayment_date:
                if total_paid_in_period < record.expected_to_pay:
                    record.payment_status = 'overdue'
                else:
                    record.payment_status = 'on_track'
            else:
                if total_paid_in_period < record.expected_to_pay:
                    record.payment_status = 'insufficient'
                else:
                    record.payment_status = 'on_track'


    # Compute overdue amount
    @api.depends('expected_to_pay', 'payment_lines.payment_amount', 'repayment_date')
    def _compute_overdue_amount(self):
        today = fields.Date.today()
        for record in self:
            if not record.repayment_date or today <= record.repayment_date:
                record.overdue_amount = 0.0
                continue

            # Get all payments up to current date
            past_payments = record.payment_lines.filtered(
                lambda p: p.payment_date <= record.repayment_date
            )
            total_paid = sum(past_payments.mapped('payment_amount'))
            
            # Calculate overdue amount
            if total_paid < record.expected_to_pay:
                record.overdue_amount = record.expected_to_pay - total_paid
            else:
                record.overdue_amount = 0.0

