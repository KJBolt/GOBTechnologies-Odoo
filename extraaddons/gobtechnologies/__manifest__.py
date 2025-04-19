{
    'name': 'GOB Technologies',
    'version': '1.1',
    'sequence': 1,
    'module_type': 'official',
    'summary': 'Customization for GOB Technologies',
    'author': 'GeoIworks',
    'images': [],
    'depends': [
        'base',
        'web',
        'base_setup',
        'contacts',
        'stock'
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'views/modify_menuitems.xml',
        'views/customer_statement_report.xml',
        'views/hubtel_webhook.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': True,
    'assets': {
        'web.assets_frontend': [],
        'web.assets_backend': [
            'gobtechnologies/static/src/scss/custom_styles.scss',
            'gobtechnologies/static/src/js/static/src/js/hubtel_notification_systray.js',
            'gobtechnologies/static/src/xml/hubtel_notification_systray.xml',
            'gobtechnologies/static/src/js/dashboard.js',
            'gobtechnologies/static/src/xml/dashboard.xml',
        ],
    },
    'license': 'LGPL-3',
}
