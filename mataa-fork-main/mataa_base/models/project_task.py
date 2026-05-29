# -*- coding: utf-8 -*-
from odoo import models, fields

class ProjectTask(models.Model):
    _inherit = 'project.task'


    project_id = fields.Many2one(required=False)


    project_ids = fields.Many2many(
        comodel_name='project.project',
        relation='project_task_project_rel',
        column1='task_id',
        column2='project_id_col',
        string='Projects'
    )