from odoo import api, models
from odoo.exceptions import UserError


class CountryService:

    @staticmethod
    def get_country(env, country_name):
        domain = [('name', '=', country_name)]

        country = env['res.country'].search(domain, limit=1)

        return country
