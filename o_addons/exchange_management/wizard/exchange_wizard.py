from odoo import models, fields, api, _
from odoo.exceptions import UserError,ValidationError
import datetime
from odoo.addons import decimal_precision as dp


class ExchangePickingLine(models.TransientModel):
    _name = "stock.exchange.picking.line"
    _rec_name = 'product_id'
    _description = 'Exchange Picking Line'

    product_id = fields.Many2one('product.product', string="Product", required=True)
    quantity = fields.Float("Quantity", digits=dp.get_precision('Product Unit of Measure'), required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='move_id.product_uom', readonly=False)
    wizard_id = fields.Many2one('stock.return.picking', string="Wizard")
    move_id = fields.Many2one('stock.move', "Move")



class ReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    product_exchange_moves = fields.One2many('stock.exchange.picking.line', 'wizard_id', 'Exchange Products')

    def calculate_total(self,amount):
        total_exchange=0
        if amount and self.product_exchange_moves:
            for product in self.product_exchange_moves:
                if product.product_id.lst_price:
                    total_exchange += (product.product_id.lst_price * product.quantity)
            if total_exchange == amount:
                return 0,'same'
            elif total_exchange > amount:
                return abs(amount-total_exchange),'positive'
            else:
                return abs(amount-total_exchange),'negative'
        else:
            return 0,'same'

    def _prepare_move_exchange_values(self, exchange_line, created_picking):
        vals = {
            'product_id': exchange_line.product_id.id,
            'name':exchange_line.product_id.name,
            'product_uom_qty': exchange_line.quantity,
            'product_uom': exchange_line.product_id.uom_id.id,
            'picking_id': created_picking.id,
            'state': 'draft',
            'date_expected': fields.Datetime.now(),
            'location_id': self.location_id.id or exchange_line.move_id.location_id.id,
            'location_dest_id': exchange_line.move_id.location_dest_id.id or self.original_location_id.id,
            'picking_type_id': created_picking.picking_type_id.id,
            'warehouse_id': self.picking_id.picking_type_id.warehouse_id.id,
            'origin_returned_move_id': exchange_line.move_id.id,
            'procure_method': 'make_to_stock',
        }
        return vals

    def _create_exchange_returns(self):
        picking_type_id =self.picking_id.picking_type_id.id
        vals={
            'move_lines': [],
            'picking_type_id': picking_type_id,
            'state': 'draft',
            'origin': _("Exchange of %s") % self.picking_id.name,
            'location_id': self.location_id.id,
            'location_dest_id': self.picking_id.location_dest_id.id
            }
        created_picking=self.picking_id.copy(vals)
        exchange_lines = 0

        for exchange_line in self.product_exchange_moves:
            if exchange_line.quantity:
                exchange_lines += 1
                vals=self._prepare_move_exchange_values(exchange_line, created_picking)
                exchange_move=self.env['stock.move'].create(vals)
                vals = {}
                move_orig_to_link = exchange_line.move_id.move_dest_ids.mapped('returned_move_ids')
                move_dest_to_link = exchange_line.move_id.move_orig_ids.mapped('returned_move_ids')
                vals['move_orig_ids'] = [(4, m.id) for m in move_orig_to_link | exchange_line.move_id]
                vals['move_dest_ids'] = [(4, m.id) for m in move_dest_to_link]
                exchange_move.write(vals)
        if not exchange_lines:
            raise UserError(_("Please specify at least one non-zero quantity."))

        created_picking.action_confirm()
        created_picking.action_assign()
        return created_picking.id

    def _create_exchange(self):
        amount=0
        total=0
        create_type='same'
        order=0
        invoice = ''
        created_picking_id=0
        inv_obj=self.env['account.invoice']

        if self.product_exchange_moves and self.picking_id:
            if self.picking_id.purchase_id:
                order=self.picking_id.purchase_id
                amount =self.picking_id.purchase_id.amount_total
            elif self.picking_id.sale_id:
                order=self.picking_id.sale_id
                amount =self.picking_id.sale_id.amount_total
            else:
                raise ValidationError("Please provide correct type of transfer")

            total,create_type=self.calculate_total(amount)  #For finding the type of invoice to be created
            exchange_product=self.env['product.product'].search([('is_exchange','=',True)],limit=1)
            refund_product=self.env['product.product'].search([('is_exchange','=',True)],limit=1)

            if not exchange_product or not refund_product:
                raise ValidationError("Please provide products for the exchange or return process to be done")

            if total !=0 and create_type != 'same':
                if create_type =='positive':
                    invoice = inv_obj.create({
                        'name': order.name,
                        'origin': order.name,
                        'type': 'out_invoice' if self.picking_id.sale_id else 'in_invoice',
                        'reference': False,
                        'account_id': order.partner_id.property_account_receivable_id.id,
                        'partner_id': order.partner_id.id,
                        'invoice_line_ids': [(0, 0, {
                            'name': exchange_product.name,
                            'origin': order.name,
                            'account_id': order.partner_id.property_account_receivable_id.id,
                            'price_unit': total,
                            'quantity': 1,
                            'discount': 0.0,
                            'uom_id': exchange_product.uom_id.id,
                            'product_id': exchange_product.id,
                        })],
                    })

                else:
                    invoice = inv_obj.create({
                        'name': order.name,
                        'origin': order.name,
                        'type': 'out_refund' if self.picking_id.sale_id else 'in_refund',
                        'reference': False,
                        'account_id': order.partner_id.property_account_receivable_id.id,
                        'partner_id': order.partner_id.id,
                        'invoice_line_ids': [(0, 0, {
                            'name': refund_product.name,
                            'origin': order.name,
                            'account_id': order.partner_id.property_account_receivable_id.id,
                            'price_unit': total,
                            'quantity': 1,
                            'discount': 0.0,
                            'uom_id': refund_product.uom_id.id,
                            'product_id': refund_product.id,
                        })],
                    })
                invoice.compute_taxes()
            created_picking_id=self._create_exchange_returns() # Exchange occurs here
        return created_picking_id


    def make_exchange(self):
        created_picking_id=0
        new_picking_id=0
        pick_type_id=0
        for wizard in self:
            if wizard.product_return_moves:
                new_picking_id, pick_type_id = wizard._create_returns()
            if wizard.product_exchange_moves:
                created_picking_id=wizard._create_exchange()
        view = self.env.ref("stock.vpicktree", False) or self.env['ir.ui.view']
        return {
            'name': _('Returned & Exchanged Picking'),
            'view_mode': 'tree',
            'views': [(view.id, "list")],
            'res_model': 'stock.picking',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', [new_picking_id,created_picking_id,self.picking_id.id if self.picking_id else 0])],
        }
