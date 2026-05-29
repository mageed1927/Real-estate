# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    endpoint_url = fields.Char(string="Endpoint Url", config_parameter="mataa_s3.endpoint_url", help="S3 Endpoint Url")
    region = fields.Char(string="Region", config_parameter="mataa_s3.region", help="S3 Region")
    access_key_id = fields.Char(string="Access Key ID", config_parameter="mataa_s3.access_key_id", help="S3 Access Key ID")
    secret_access_key = fields.Char(string="Secret Access Key", config_parameter="mataa_s3.secret_access_key", help="S3 Secret Access Key")
    bucket = fields.Char(string="Bucket", config_parameter="mataa_s3.bucket", help="S3 Bucket")
    public_cdn_url = fields.Char(string="Public Cdn Url", config_parameter="mataa_s3.public_cdn_url", help="Public CDN Url")