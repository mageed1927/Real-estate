from odoo import models, fields

class ProductImageBulkWizard(models.TransientModel):
    _name = 'product.image.bulk.wizard'
    _description = 'Wizard to Upload Multiple Images'

    product_tmpl = fields.Many2one('product.template')
    attachment_ids = fields.Many2many('ir.attachment', string="Images")

    def action_upload_images(self):
        existing_sequences = self.product_tmpl.image_url_ids.mapped('sequence')
        if existing_sequences:
            current_sequence = max(existing_sequences) + 1
        else:
            current_sequence = 0
        
        image_commands = []
        for attachment in self.attachment_ids:
            image_data_str = attachment.datas.decode('utf-8') if attachment.datas else False

            image_commands.append((0, 0, {
                'file_name': attachment.name,
                'file_data': image_data_str,
                'sequence': current_sequence,
                'url': False
            }))

            current_sequence += 1
            
        if image_commands:
            self.product_tmpl.write({
                'image_url_ids': image_commands
            })
    
        return {'type': 'ir.actions.act_window_close'}
