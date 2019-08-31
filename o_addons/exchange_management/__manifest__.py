# -*- coding: utf-8 -*-

{
    'name': 'Exchange management',
    'version': '1.0',
    'summary': """Exchange test case""",
    'description': """Exchange Management""",
    'author': 'Vishnu M Nair',
    'company': '',
    'website': '',
    'category': 'Products',
    'depends': ['base', 'account','sale_management','purchase','stock','product'],
    'license': 'AGPL-3',
    'data': [
        'views/product_form_view.xml',
        'views/exchange_products_view.xml',
        'wizard/exchange_wizard_view.xml',
        'security/ir.model.access.csv',
        'data/products_data.xml'

    ],
    'qweb': [],
    'demo': [],
    'images': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
