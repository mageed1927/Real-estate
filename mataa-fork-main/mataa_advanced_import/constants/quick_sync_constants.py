# -*- coding: utf-8 -*-
from odoo.http import request


class QuickSyncConstants:

    @staticmethod
    def get_env():
        return request.env if request else None

    @staticmethod
    def get_quick_update_url():
        env = QuickSyncConstants.get_env()
        return env['ir.config_parameter'].sudo().get_param('mataa_advanced_import.quick_sync_url')

    # @staticmethod
    # def get_quick_update_url():
    #     return 'http://68.183.69.211:5024/Product/OdooStockUpdate'

