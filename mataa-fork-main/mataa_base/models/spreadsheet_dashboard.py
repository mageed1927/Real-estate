from odoo import api, fields, models

class SpreadsheetDashboard(models.Model):
    _inherit = "spreadsheet.dashboard"

    stored_group_id = fields.Many2one(
        "spreadsheet.dashboard.group",
        string="Stored Group",
        help="المجموعة الدائمة التي نعيدها بعد أي ترقية/تشغيل."
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # عند الإنشاء: خزّن المجموعة الحالية كقيمة دائمة
            if rec.dashboard_group_id and not rec.stored_group_id:
                rec.stored_group_id = rec.dashboard_group_id.id
        return records

    def write(self, vals):
        res = super().write(vals)
        # التغيير الصحيح يكون على dashboard_group_id
        if "dashboard_group_id" in vals:
            for rec in self:
                if rec.dashboard_group_id and rec.stored_group_id != rec.dashboard_group_id:
                    rec.stored_group_id = rec.dashboard_group_id.id
        return res

    @api.model
    def cron_reassign_spreadsheet_groups(self):
        """شبكة أمان: طبّق stored_group_id لكل الـspreadsheets."""
        dashboards = self.search([])
        for d in dashboards:
            if not d.stored_group_id and d.dashboard_group_id:
                d.stored_group_id = d.dashboard_group_id.id
            if d.stored_group_id and d.dashboard_group_id.id != d.stored_group_id.id:
                d.dashboard_group_id = d.stored_group_id.id
