from odoo import SUPERUSER_ID
from odoo.api import Environment

def reassign_spreadsheet_groups(cr, registry):
    env = Environment(cr, SUPERUSER_ID, {})
    dashboards = env["spreadsheet.dashboard"].search([])
    for d in dashboards:
        if not d.stored_group_id and d.dashboard_group_id:
            d.stored_group_id = d.dashboard_group_id.id
        if d.stored_group_id and d.dashboard_group_id.id != d.stored_group_id.id:
            d.dashboard_group_id = d.stored_group_id.id
