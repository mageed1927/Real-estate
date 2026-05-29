from odoo import models, fields, api
from odoo.exceptions import UserError
from ...mataa_s3.services.s3_service import S3Service
from ..utility.image_utility import ImageUtility
from ..utility.file_utility import FileUtility
from ..constants.image_constants import IMAGE_SIZES

class ProductPublicCategory(models.Model):
    _inherit = "product.public.category"

    image_url = fields.Char(string="Image URL", help="S3 URL for the category image.")
    seo_keyword_ids = fields.Many2many(
        'product.seo.keyword',
        'product_public_category_seo_rel',
        'category_id',
        'seo_id',
        string='SEO Keywords',
        help='SEO keywords for this website category.'
    )

    def clear_image(self):
        self.write({'image_url': False})

    def _upload_image_to_s3(self, image_data, file_name=None):
        if not image_data:
            return None, None
        file_name = file_name or f"category_image_{self.id or 'new'}.png"
        serialized_name = S3Service.sanitize_file_name(file_name)
        file_remote_url = S3Service.upload_file(env=self.env, file_name=serialized_name, file_data=image_data)
        # Optionally upload resized versions
        resized_images = ImageUtility.resize_images(image_data)
        for size_name, resized_data in resized_images.items():
            base_name, ext = FileUtility.extract_extension(serialized_name)
            resized_file_name = f"{base_name}_{size_name}{ext}"
            S3Service.upload_file(env=self.env, file_name=resized_file_name, file_data=resized_data)
        return file_remote_url, serialized_name

    def _propagate_seo_keywords_to_products(self, old_seos_map=None):
        product_add_map = {}
        product_remove_map = {}
        for category in self:
            new_seos = set(category.seo_keyword_ids.ids)
            old = set() if old_seos_map is None else old_seos_map.get(category.id, set())
            added = new_seos - old
            removed = old - new_seos
            products = self.env['product.template'].search([('public_categ_ids', 'in', category.id)])
            for product in products:
                product_seos = set(product.product_seo_keywords.ids)

                to_add = set(added - product_seos)
                if to_add:
                    product_add_map.setdefault(product.id, set()).update(to_add)

                if removed:
                    other_categs = product.public_categ_ids.filtered(lambda c: c.id != category.id)
                    other_seos = set()
                    for cat in other_categs:
                        other_seos |= set(cat.seo_keyword_ids.ids)
                    to_remove = set([seo_id for seo_id in removed if seo_id not in other_seos])
                    if to_remove:
                        product_remove_map.setdefault(product.id, set()).update(to_remove)

        for product_id, add_ids in product_add_map.items():
            if add_ids:
                self.env['product.template'].browse(product_id).write({'product_seo_keywords': [(4, seo_id) for seo_id in add_ids]})
        for product_id, remove_ids in product_remove_map.items():
            if remove_ids:
                self.env['product.template'].browse(product_id).write({'product_seo_keywords': [(3, seo_id) for seo_id in remove_ids]})

    def force_propagate_seo_keywords(self):
        products = self.env['product.template'].search([('public_categ_ids', 'in', self.ids)])
        products._propagate_seo_keywords_on_category_change(force=True)

    @api.model
    def create(self, vals):
        image_data = vals.get('image_1920')
        if image_data:
            file_remote_url, serialized_name = self._upload_image_to_s3(image_data, vals.get('name', 'category_image'))
            vals['image_url'] = file_remote_url
            vals['image_1920'] = False  # Remove binary after upload
        return super(ProductPublicCategory, self).create(vals)

    def update_children_names(self, old_name, new_name):
        for category in self:
            children = category.child_id
            for child in children:
                updated_name = '/'.join(part.replace(old_name, new_name) if part.strip() == old_name else part for part in child.name.split('/'))
                self.with_context(skip_sync=True).env['product.public.category'].browse(child.id).write({'name': updated_name})

    def write(self, vals):
        # --- SEO propagation logic ---
        seo_field = 'seo_keyword_ids'
        seo_changed = False
        old_seos = {}
        if seo_field in vals:
            seo_changed = True
            for category in self:
                old_seos[category.id] = set(category.seo_keyword_ids.ids)

        image_data = vals.get('image_1920')
        if image_data:
            # Delete old image from S3 if exists
            for rec in self:
                if rec.image_url:
                    try:
                        old_serialized_name = rec.image_url.split('/')[-1]
                        S3Service.delete_file(self.env, old_serialized_name)
                        for size_name in IMAGE_SIZES.keys():
                            base_name, ext = FileUtility.extract_extension(old_serialized_name)
                            resized_file_name = f"{base_name}_{size_name}{ext}"
                            if S3Service.check_file_exists(self.env, resized_file_name):
                                S3Service.delete_file(self.env, resized_file_name)
                    except Exception as e:
                        pass  # Optionally log
            file_remote_url, serialized_name = self._upload_image_to_s3(image_data)
            vals['image_url'] = file_remote_url
            vals['image_1920'] = False
        if 'name' in vals:
            old_name = self.name
        res = super(ProductPublicCategory, self).write(vals)
        if old_name:
            self.update_children_names(old_name, vals['name'])
        if seo_changed:
            self._propagate_seo_keywords_to_products(old_seos_map=old_seos)
        return res

    def unlink(self):
        for rec in self:
            if rec.image_url:
                try:
                    serialized_name = rec.image_url.split('/')[-1]
                    S3Service.delete_file(self.env, serialized_name)
                    for size_name in IMAGE_SIZES.keys():
                        base_name, ext = FileUtility.extract_extension(serialized_name)
                        resized_file_name = f"{base_name}_{size_name}{ext}"
                        if S3Service.check_file_exists(self.env, resized_file_name):
                            S3Service.delete_file(self.env, resized_file_name)
                except Exception as e:
                    pass  # Optionally log
        return super(ProductPublicCategory, self).unlink()