from odoo import api, fields, models


class LogImports(models.Model):
    _name = 'log.imports'
    _description = 'History of imports'

    date = fields.Datetime('Time', default=lambda self: fields.Datetime.now())
    import_type = fields.Selection([('quick', 'Quick import'), ('advanced', 'Advanced import')], string="Type",
                                   default="quick")
    file_name = fields.Char('File name')
