import base64
from datetime import datetime
from odoo import models, fields, api
import boto3
from odoo.exceptions import UserError
from io import BytesIO
import mimetypes
import logging

_logger = logging.getLogger(__name__)

class S3Service:

    @staticmethod
    def _get_s3_client(env):
        params = {
            'endpoint_url': env['ir.config_parameter'].sudo().get_param('mataa_s3.endpoint_url'),
            'aws_access_key_id': env['ir.config_parameter'].sudo().get_param('mataa_s3.access_key_id'),
            'aws_secret_access_key': env['ir.config_parameter'].sudo().get_param('mataa_s3.secret_access_key'),
            'region_name': env['ir.config_parameter'].sudo().get_param('mataa_s3.region'),
        }
        if (params['endpoint_url'] and params['aws_access_key_id']
        and params['aws_secret_access_key'] and params['region_name']):
            return boto3.client('s3', **params)
        else:
            raise UserError("S3 settings are invalid, please revise them and try again")

    @staticmethod
    def _get_default_bucket_name(env):
        return env['ir.config_parameter'].sudo().get_param('mataa_s3.bucket')

    @staticmethod
    def _get_cdn_file_url(env, file_name):
        public_cdn_url = env['ir.config_parameter'].sudo().get_param('mataa_s3.public_cdn_url')
        return f"{public_cdn_url}/{file_name}"

    @staticmethod
    def sanitize_file_name(file_name):
        file_name = file_name.lower().replace(' ', '_')

        if '.' in file_name:
            parts = file_name.split('.')
            base_name = '_'.join(parts[:-1])  # Join all parts except the last one with underscores
            ext = parts[-1]  # Last part as the extension
        else:
            base_name = file_name
            ext = ''

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]
        unique_file_name = f"{base_name}_{timestamp}.{ext}" if ext else f"{base_name}_{timestamp}"

        return unique_file_name

    @staticmethod
    def upload_file(env, file_name, file_data):
        s3 = S3Service._get_s3_client(env)
        bucket_name = S3Service._get_default_bucket_name(env)
        content_type, _ = mimetypes.guess_type(file_name)
        if not content_type:
            content_type = 'application/octet-stream'

        extra_args = {
                'ACL': 'public-read',
                'ContentType': content_type,
                'CacheControl': 'max-age=31536000'
                    }

        # unique_file_name = S3Service._sanitize_file_name(file_name)

        try:
            if isinstance(file_data, str):
                file_data = base64.b64decode(file_data)

            file_stream = BytesIO(file_data)

            s3.upload_fileobj(file_stream, bucket_name, file_name, ExtraArgs=extra_args)

            file_url = S3Service._get_cdn_file_url(env, file_name)

            _logger.info(f"Image {file_url} uploaded to S3 successfully")

            return file_url

        except Exception as e:
            raise UserError(f"Failed to upload file {file_name} to S3: {str(e)}")

    @staticmethod
    def get_file_info(env, file_name):
        s3 = S3Service._get_s3_client(env)
        bucket_name = S3Service._get_default_bucket_name(env)

        try:
            file_info = s3.get_object(Bucket=bucket_name, Key=file_name)

            return file_info
        except Exception as e:
            raise UserError(f"Failed to get file {file_name} info : {str(e)}")

    @staticmethod
    def check_file_exists(env, file_name):
        s3 = S3Service._get_s3_client(env)
        bucket_name = S3Service._get_default_bucket_name(env)

        try:
            s3.head_object(Bucket=bucket_name, Key=file_name)
            return True
        except Exception as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                raise UserError(f"Failed to get file {file_name} info : {str(e)}")

    @staticmethod
    def download_file(env, object_name, file_name):
        s3 = S3Service._get_s3_client(env)
        bucket_name = S3Service._get_default_bucket_name(env)

        try:
            s3.download_file(bucket_name, object_name, file_name)
        except Exception as e:
            raise UserError(f"Failed to download file {file_name} from S3: {str(e)}")
        return True

    @staticmethod
    def delete_file(env, filename):
        s3 = S3Service._get_s3_client(env)
        bucket_name = S3Service._get_default_bucket_name(env)
        fileurl = S3Service._get_cdn_file_url(env, filename)
        try:
            s3.delete_object(Bucket=bucket_name, Key=filename)
            _logger.info(f"Image {fileurl} deleted from S3 successfully")
        except Exception as e:
            raise UserError(f"Failed to delete file {filename} from S3: {str(e)}")
        return True
