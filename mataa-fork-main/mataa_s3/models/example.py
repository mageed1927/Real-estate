# # -*- coding: utf-8 -*-
#
# from odoo import models, fields, api
# from odoo.exceptions import UserError
# from ..services.s3_service import S3Service
#
#
# class Example(models.Model):
#     _name = 'mataa.s3.example'
#     _description = 'example of mataa.s3.example model'
#
#     name = fields.Char(string='Name', required=True)
#     file_name = fields.Char(string='File Name')
#     file_data = fields.Binary(string='File Data', required=True)
#     file_remote_url = fields.Char(string='File Remote Url', readonly=True)
#
#     # def write(self, vals):
#     #     updated = super(Example, self).write(vals)
#     #     if 'file_data' in vals and vals['file_data']:
#     #         file_data = vals['file_data']
#     #         file_remote_url = S3Service.upload_file(self.env, updated.file_name, file_data)
#     #     return updated
#
#     @api.model
#     def create(self, vals):
#         vals['file_name'] = S3Service.sanitize_file_name(vals['file_name'])
#
#         if 'file_data' in vals and vals['file_data']:
#             file_data = vals['file_data']
#             file_remote_url = S3Service.upload_file(self.env, vals['file_name'], vals['file_data'])
#             vals['file_remote_url'] = file_remote_url
#         return super(Example, self).create(vals)
#
#     def unlink(self):
#         for record in self:
#             try:
#                 S3Service.delete_file(self.env, record.file_name)
#             except Exception as e:
#                 raise UserError(f"Error deleting file {record.file_name} from S3: {str(e)}")
#             super(Example, record).unlink()
