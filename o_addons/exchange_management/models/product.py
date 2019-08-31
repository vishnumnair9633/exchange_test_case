# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_refund = fields.Boolean(string='Refund ?')
    is_exchange=fields.Boolean(string="Exchange ?")
