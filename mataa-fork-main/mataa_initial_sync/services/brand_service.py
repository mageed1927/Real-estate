from odoo import api, models
from odoo.exceptions import UserError


class BrandService:

    @staticmethod
    def get_brand(env, brand_id):
        domain = [('id', '=', brand_id)]

        brand = env['product.brand'].search(domain, limit=1)

        return brand

    @staticmethod
    def get_brand_by_name(env, brand_name):
        domain = [('name', '=', brand_name)]

        brand = env['product.brand'].search(domain, limit=1)

        return brand

    @staticmethod
    def update_brand(env, brand_id, name, mataa_id):
        brand = BrandService.get_brand(env, brand_id)
        if not brand:
            raise UserError(f"brand {name} wasn't found with the id of {brand_id}")

        brand.write({
            'mataa_id': mataa_id,
            'is_synced': True
        })

        return brand

