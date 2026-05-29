from odoo import api, models
from odoo.exceptions import UserError


class BrandService:

    @staticmethod
    def get_brand_by_name(env, brand_name):
        domain = [('name', '=', brand_name)]

        brand = env['product.brand'].sudo().search(domain, limit=1)

        return brand
