# # -*- coding: utf-8 -*-

from odoo import models, fields, api, SUPERUSER_ID


class MataaPrecreationEmployee(models.Model):
    _name = 'mataa.precreation.employee'
    _description = 'Mataa Precreation Employee'

    name = fields.Char(string='Employee Name', required=True)
    employee_id = fields.Many2one('hr.employee')

    @api.model
    def create(self, vals):
        employee = self.env['hr.employee'].with_user(SUPERUSER_ID).create({
            'name': vals['name'],
        })
        vals['employee_id'] = employee.id
        return super(MataaPrecreationEmployee, self).create(vals)
