from odoo import api, fields, models, _
from datetime import timedelta
from dateutil.relativedelta import relativedelta 
import logging
from odoo.exceptions import ValidationError
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

    # Computes the next repayment date
    # @api.depends('start_date', 'repayment_frequency', 'last_repayment_date', 'payment_lines.payment_date')
    # def _compute_repayment_date(self):
    #     for record in self:
    #         if not record.start_date or not record.repayment_frequency:
    #             record.repayment_date = False
    #             continue

    #         # Get all payment lines sorted by date
    #         sorted_payments = record.payment_lines.sorted(lambda p: p.payment_date)

    #         if record.start_date and record.repayment_frequency and not sorted_payments:
    #             if record.repayment_frequency == '1':  # Daily
    #                 next_date = record.start_date + timedelta(days=1)
    #             elif record.repayment_frequency == '7':  # Weekly
    #                 next_date = record.start_date + timedelta(weeks=1)
    #             elif record.repayment_frequency == '30':  # Monthly
    #                 next_date = record.start_date + relativedelta(months=1)
    #             else:  # Cash
    #                 next_date = record.start_date

    #             record.repayment_date = next_date

    #         elif record.start_date and record.repayment_frequency and sorted_payments:
    #             # # check if last payment date was within the repayment frequency period
    #             # last_payment = sorted_payments[-1].payment_date
    #             # if last_payment and (fields.Date.today() - last_payment).days <= int(record.repayment_frequency):
    #             #     _logger.info('Last payment was within the repayment frequency period')

    #             #     all_payment_within_period = self.env['repayment.payment.line'].search([
    #             #         ('repayment_id', '=', record.id),
    #             #         ('payment_date', '<=', record.repayment_date)
    #             #         ('payment_amount', '<', record.expected_to_pay)
    #             #     ])

    #             #     for record in all_payment_within_period:
    #             #         _logger.info(f"All payments Less that expected, {record.payment_amount}")


    #             #Calculate total payments within frequency period
    #             frequency_days = int(record.repayment_frequency)
    #             _logger.info(f"Frequency days: {frequency_days}")
    #             recent_date = fields.Date.today() - timedelta(days=frequency_days)
    #             _logger.info(f"Recent date: {recent_date}")
                
    #             # Get all payments within frequency period
    #             recent_payments = record.payment_lines.filtered(
    #                 lambda p: p.payment_date <= recent_date
    #             )
    #             _logger.info(f"Recent payments: {recent_payments}")
    #             total_recent_payment = sum(recent_payments.mapped('payment_amount'))
    #             _logger.info(f"Total Recent payments: {total_recent_payment}")

    #             if total_recent_payment >= record.expected_to_pay:
    #                 if record.repayment_frequency == '1':  # Daily
    #                     next_date = record.repayment_date + timedelta(days=1)
    #                 elif record.repayment_frequency == '7':  # Weekly
    #                     next_date = record.repayment_date + timedelta(weeks=1)
    #                 elif record.repayment_frequency == '30':  # Monthly
    #                     next_date = record.repayment_date + relativedelta(days=30)
    #                 else:  # Cash
    #                     next_date = record.repayment_date

    #                 record.repayment_date = next_date
    #                 _logger.info(f"Total payments within period: {total_recent_payment} meets expected amount: {record.expected_to_pay}")
    #             else:
    #                 _logger.info(f"Total payments within period: {total_recent_payment} is less than expected: {record.expected_to_pay}")
    #         else:
    #             _logger.info('Last payment was not within the repayment frequency period')


    #         # # If no last repayment date exists, use start_date as base
    #         # if not record.last_repayment_date:
    #         #     base_date = record.start_date
    #         # else:
    #         #     # Use the last repayment date as base
    #         #     base_date = record.last_repayment_date

    #         # # Calculate next repayment date based on frequency
    #         # if record.repayment_frequency == '1':  # Daily
    #         #     next_date = base_date + timedelta(days=1)
    #         # elif record.repayment_frequency == '7':  # Weekly
    #         #     next_date = base_date + timedelta(weeks=1)
    #         # elif record.repayment_frequency == '30':  # Monthly
    #         #     next_date = base_date + relativedelta(days=30)
    #         # else:  # Cash
    #         #     next_date = base_date

    #         # record.repayment_date = next_date
    #         # _logger.info(f"Start date: {record.start_date}, Base date: {base_date}, Next repayment date: {next_date}")

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
                
                if repayment.repayment_frequency == '1':  # Daily
                    should_remind = tomorrow == repayment.repayment_date
                    is_overdue = yesterday == repayment.repayment_date
                elif repayment.repayment_frequency == '14':  # Weekly
                    days_until_payment = (repayment.repayment_date - tomorrow).days
                    days_since_payment = (today - repayment.repayment_date).days
                    should_remind = days_until_payment == 0
                    is_overdue = days_since_payment == 1
                elif repayment.repayment_frequency == '30':  # Monthly
                    days_until_payment = (repayment.repayment_date - tomorrow).days
                    days_since_payment = (today - repayment.repayment_date).days
                    should_remind = days_until_payment == 0
                    is_overdue = days_since_payment == 1
                elif repayment.repayment_frequency == '0':  # Cash
                    continue
                
                # Send reminder for upcoming payment
                if should_remind and repayment.outstanding_loan > 0:
                    reminder_message = (
                        f"Dear {repayment.customer_name.name}, "
                        f"this is a reminder that your payment of GHS {repayment.expected_to_pay} "
                        f"is due tomorrow {tomorrow.strftime('%d-%m-%Y')}. "
                        f"Your outstanding balance is GHS {repayment.outstanding_loan}. "
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
                            f"your payment of GHS {repayment.expected_to_pay} was due yesterday "
                            f"but was {payment_status}. "
                            f"Your outstanding balance is GHS {repayment.outstanding_loan}. "
                            f"Please make your payment as soon as possible to avoid any penalties. "
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
            
            except Exception as e:
                raise ValidationError(f"Failed to send message to {repayment.customer_name.name}: {str(e)}")
                _logger.error(f"Failed to send message to {repayment.customer_name.name}: {str(e)}")

