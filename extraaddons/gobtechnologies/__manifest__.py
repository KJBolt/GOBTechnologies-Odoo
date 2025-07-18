{
    'name': 'SplitPay',
    'version': '1.1',
    'sequence': 1,
    'module_type': 'official',
    'summary': 'Customization for SplitPay',
    'author': 'GeoIworks',
    'images': [],
    'depends': [
        'base_setup',
        'web',
        'base', 
        'contacts'
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'views/modify_menuitems.xml',
        'views/customer_statement_report.xml',
        'views/login_template.xml',
        'views/hubtel_webhook.xml',
        'views/res_config_settings_views.xml',
        'views/payment_notifications.xml',
        'data/ir_cron.xml',
        'data/ir_sequence_data.xml',
        'views/favicon_template.xml',
    ],
    'installable': True,
    'application': True,
    'assets': {
        'web.assets_frontend': [
            'gobtechnologies/static/src/scss/custom_styles.scss',
            'gobtechnologies/static/src/js/static/src/js/change_title.js',
        ],
        'web.assets_backend': [
            'gobtechnologies/static/src/scss/custom_styles.scss',
            'gobtechnologies/static/src/js/static/src/js/hubtel_notification_systray.js',
            'gobtechnologies/static/src/xml/hubtel_notification_systray.xml',
            'gobtechnologies/static/src/js/static/src/js/change_title.js',
        ],
    },
    'license': 'LGPL-3',
}
