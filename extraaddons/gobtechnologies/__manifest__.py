{
    'name': 'GOB Technologies',
    'version': '1.1',
    'sequence': 99,
    'module_type': 'official',
    'summary': 'Customization for GOB Technologies',
    'author': 'GeoIworks',
    'images': [],
    'depends': [
        'base_setup',
        'web',
        'base', 
        'contacts', 
        'stock'
    ],
    'data': [
        'views/modify_meuitems.xml',
        'views/customer_statement_report.xml',
        'views/hubtel_webhook.xml',
        'security/groups.xml',
        'security/ir.model.access.csv',

    ],
    'installable': True,
    'application': True,
    'assets': {
        'web.assets_frontend': [],
        'web.assets_backend': [
            'gobtechnologies/static/src/js/static/src/js/hubtel_notification_systray.js',
            'gobtechnologies/static/src/xml/hubtel_notification_systray.xml',
        ],
    },
    'license': 'LGPL-3',
}