{
    'name': 'GOB Technologies',
    'version': '1.1',
    'sequence': 1,
    'module_type': 'official',
    'summary': 'Customization for GOB Technologies',
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
        # 'views/hubtel_webhook.xml',
        'views/res_config_settings_views.xml',
        'views/payment_notifications.xml',
        'data/ir_cron.xml',
    ],
    'installable': True,
    'application': True,
    'assets': {
        'web.assets_frontend': [
            'gobtechnologies/static/src/scss/custom_styles.scss',
        ],
        'web.assets_backend': [
            'gobtechnologies/static/src/scss/custom_styles.scss',
            'gobtechnologies/static/src/js/static/src/js/hubtel_notification_systray.js',
            'gobtechnologies/static/src/xml/hubtel_notification_systray.xml',
        ],
    },
    'license': 'LGPL-3',
}
