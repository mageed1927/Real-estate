from odoo import models, fields, api
from odoo.exceptions import UserError


class QuantPackage(models.Model):
    _inherit = "stock.quant.package"

    location_id = fields.Many2one(
        "stock.location",
        "Location",
        compute=False,
        store=True,
        required=True,
        default=18,
    )

    package_use = fields.Selection(default="reusable", readonly=True)

    @api.constrains("name", "location_id")
    def _check_duplicated_name_location(self):
        for package in self:
            domain = [
                ("name", "=", package.name),
                ("location_id", "=", package.location_id.id),
            ]
            if self.search_count(domain) > 1:
                raise UserError(
                    "Packages can't have the same name in the same location"
                )

    @api.depends("quant_ids.package_id", "quant_ids.company_id", "quant_ids.owner_id")
    def _compute_package_info(self):

        for package in self:
            values = {
                "location_id": False,
                "company_id": self.env.user.company_id.id,
                "owner_id": False,
            }
            if self.quant_ids:
                values["location_id"] = self.quant_ids[0].location_id
            package.package_use = "reusable"
            package.company_id = values["company_id"]
            package.owner_id = values["owner_id"]

    def unpack(self):
        return super(
            QuantPackage, self.with_context(skip_mataa_quant_sync=True)
        ).unpack()

