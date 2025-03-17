odoo.define('gobtechnologies.hubtel_payment', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');

    publicWidget.registry.HubtelPayment = publicWidget.Widget.extend({
        selector: '#hubtel_payment',
        events: {
            'click': '_onHubtelPaymentSelected',
        },

        _onHubtelPaymentSelected: async function (event) {
            event.preventDefault();
            console.log("You selected Hubtel Payment. Click Pay Now to proceed.");

            // Modify Pay Now button action
            // document.querySelector('.oe_sale_acquirer_button').addEventListener('click', async function(event) {
            //     event.preventDefault(); // Prevent default Odoo behavior

            //     let orderAmount = 230.00;  // Get from the page dynamically
            //     let phone = document.getElementById('customer_phone').value;
            //     let reference = document.getElementById('order_reference').textContent;

            //     let response = await fetch('/hubtel/payment/initiate', {
            //         method: 'POST',
            //         headers: { 'Content-Type': 'application/json' },
            //         body: JSON.stringify({
            //             amount: orderAmount,
            //             phone: phone,
            //             reference: reference,
            //             description: "Order Payment",
            //         }),
            //     });

            //     let data = await response.json();
            //     if (data.responseCode === '0000') {
            //         window.location.href = data.checkoutUrl; // Redirect to Hubtel
            //     } else {
            //         alert("Payment failed: " + data.responseMessage);
            //     }
            // });
        }
    });

    return publicWidget.registry.HubtelPayment;
});
