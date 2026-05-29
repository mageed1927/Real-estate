from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
from ...mataa_s3.services.s3_service import S3Service
from ..utility.image_utility import ImageUtility
from ..utility.file_utility import FileUtility
from ..constants.image_constants import IMAGE_SIZES

_logger = logging.getLogger(__name__)


class ProductImage(models.Model):
    _name = 'product.url'

    file_name = fields.Char(string='File Name')
    file_data = fields.Binary(string='File Data')

    product_tmpl_id = fields.Many2one(
        string='Product',
        comodel_name='product.template',
        ondelete='cascade'
    )
    product_id = fields.Many2one('product.product', string='Variant', ondelete='cascade')
    url = fields.Char(
        string='Image URL',
        help='URL of the image for showcasing your product.',
    )

    serialized_name = fields.Char(
        string="Serialized name",
        help="Serialized name that is uniquely given to this image.",
    )

    sequence = fields.Integer(
        string="No.",
        help="The order of the image",
        required=True
    )

    link_html = fields.Html(
        compute='_compute_link_html',
        string="Link",
    )

    @api.depends('url', 'serialized_name')
    def _compute_link_html(self):
        for record in self:
            if record.url:
                link_text = record.serialized_name or record.url
                record.link_html = f'<a href="{record.url}" target="_blank">{link_text}</a>'
            else:
                record.link_html = False

    def write(self, vals):

        return super(ProductImage, self).write(vals)

    @api.model
    def create(self, vals):

        if self.env.context.get('pre_sync'):
            return super(ProductImage, self).create(vals)
        
        # Validate required fields
        if not vals.get('file_name'):
            _logger.warning('Product image creation skipped: missing file_name')
            # Create record without S3 upload if file_name is missing
            vals['serialized_name'] = None
            vals['url'] = None
            vals.pop('file_data', None)
            # return super(ProductImage, self).create(vals)
            raise UserError(".لا يمكن رفع صورة بدون اسم")
        
        if not vals.get('file_data'):
            _logger.warning('Product image creation skipped: missing file_data')
            # Create record without S3 upload if file_data is missing
            vals['serialized_name'] = None
            vals['url'] = None
            vals.pop('file_data', None)
            # return super(ProductImage, self).create(vals)
            raise UserError(".لا يمكن رفع صورة فارغة")
        
        try:
            serialized_name = S3Service.sanitize_file_name(vals['file_name'])
            file_remote_url = S3Service.upload_file(env=self.env, file_name=serialized_name,
                                                    file_data=vals['file_data'])
            resized_images = ImageUtility.resize_images(vals['file_data'])

            for size_name, resized_data in resized_images.items():
                base_name, ext = FileUtility.extract_extension(serialized_name)
                resized_file_name = f"{base_name}_{size_name}{ext}"

                S3Service.upload_file(env=self.env, file_name=resized_file_name, file_data=resized_data)
            
            vals['serialized_name'] = serialized_name
            vals['url'] = file_remote_url
            vals.pop('file_data', None)

        except UserError as e:
            # Re-raise UserError as-is (these are expected errors from S3Service)
            _logger.error(f'Failed to upload product image {vals.get("file_name", "unknown")} to S3: {str(e)}')
            raise
        except Exception as e:
            # Log the actual error with details but don't include binary data
            error_details = {
                'file_name': vals.get('file_name'),
                'error': str(e),
                'error_type': type(e).__name__
            }
            _logger.error(f'Unexpected error uploading product image: {error_details}')
            raise UserError(
                f"Failed to upload product image '{vals.get('file_name', 'unknown')}' to S3. "
                f"Error: {str(e)}"
            )

        return super(ProductImage, self).create(vals)

    def unlink(self):
        for record in self:
            try:
                S3Service.delete_file(self.env, record.serialized_name)

                for size_name, size in IMAGE_SIZES.items():
                    base_name, ext = FileUtility.extract_extension(record.serialized_name)
                    resized_file_name = f"{base_name}_{size_name}{ext}"

                    if S3Service.check_file_exists(self.env, resized_file_name):
                        S3Service.delete_file(self.env, resized_file_name)

                super(ProductImage, record).unlink()

            except Exception as e:
                raise UserError(f"Error deleting file {record.file_name} from S3: {str(e)}")

        return True
