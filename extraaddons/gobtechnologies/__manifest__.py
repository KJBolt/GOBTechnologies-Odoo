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
        'views/repayment.xml'
    ],
    'installable': True,
    'application': True,
    'assets': {
        'web.assets_backend': [],
    },
    'license': 'LGPL-3',
}