from odoo import models, fields, api
from odoo.exceptions import UserError
from ...mataa_s3.services.s3_service import S3Service
from ..utility.image_utility import ImageUtility
from ..utility.file_utility import FileUtility
from ..constants.image_constants import IMAGE_SIZES

class ProductBrand(models.Model):
    _inherit = "product.brand"

    logo_url = fields.Char(string="Logo URL", help="S3 URL for the brand logo.")

    seo_keyword_ids = fields.Many2many(
        'product.seo.keyword',
        'product_brand_seo_rel',
        'brand_id',
        'seo_id',
        string='SEO Keywords',
        help='SEO keywords for products of this brand.'
    )

    def clear_image(self):
        self.write({'logo_url': False})

    def _get_brand_field_on_product(self):
        Product = self.env['product.template']
        return 'product_brand_id' if 'product_brand_id' in Product._fields else 'brand_id'

    def _propagate_seo_keywords_to_products(self, old_seos_map=None):
        product_add_map = {}
        product_remove_map = {}
        brand_field = self._get_brand_field_on_product()

        for brand in self:
            new_seos = set(brand.seo_keyword_ids.ids)
            old = set() if old_seos_map is None else old_seos_map.get(brand.id, set())
            added = new_seos - old
            removed = old - new_seos

            products = self.env['product.template'].search([(brand_field, '=', brand.id)])
            for product in products:
                # respect restricted keywords and avoid duplicates
                existing = set(product.product_seo_keywords.ids)
                restricted = set(product.restricted_seo_keyword_ids.ids)

                to_add = set(added) - existing - restricted
                if to_add:
                    product_add_map.setdefault(product.id, set()).update(to_add)

                # removal: only if not present via categories
                if removed:
                    cat_seos = set()
                    for c in product.public_categ_ids:
                        cat_seos |= set(c.seo_keyword_ids.ids)
                    to_remove = set(seo_id for seo_id in removed if seo_id not in cat_seos)
                    if to_remove:
                        product_remove_map.setdefault(product.id, set()).update(to_remove)

        for product_id, add_ids in product_add_map.items():
            if add_ids:
                self.env['product.template'].browse(product_id).write(
                    {'product_seo_keywords': [(4, sid) for sid in add_ids]}
                )
        for product_id, remove_ids in product_remove_map.items():
            if remove_ids:
                self.env['product.template'].browse(product_id).write(
                    {'product_seo_keywords': [(3, sid) for sid in remove_ids]}
                )

    def force_propagate_seo_keywords(self):
        brand_field = self._get_brand_field_on_product()
        for brand in self:
            products = self.env['product.template'].search([(brand_field, '=', brand.id)])
            to_add_map = {}
            for product in products:
                existing = set(product.product_seo_keywords.ids)
                restricted = set(product.restricted_seo_keyword_ids.ids)
                desired = set(brand.seo_keyword_ids.ids) - existing - restricted
                if desired:
                    to_add_map.setdefault(product.id, set()).update(desired)
            for pid, add_ids in to_add_map.items():
                self.env['product.template'].browse(pid).write(
                    {'product_seo_keywords': [(4, sid) for sid in add_ids]}
                )

    def _upload_logo_to_s3(self, logo_data, file_name=None):
        if not logo_data:
            return None, None
        file_name = file_name or f"brand_logo_{self.id or 'new'}.png"
        serialized_name = S3Service.sanitize_file_name(file_name)
        file_remote_url = S3Service.upload_file(env=self.env, file_name=serialized_name, file_data=logo_data)
        # Optionally upload resized versions
        resized_images = ImageUtility.resize_images(logo_data)
        for size_name, resized_data in resized_images.items():
            base_name, ext = FileUtility.extract_extension(serialized_name)
            resized_file_name = f"{base_name}_{size_name}{ext}"
            S3Service.upload_file(env=self.env, file_name=resized_file_name, file_data=resized_data)
        return file_remote_url, serialized_name

    @api.model
    def create(self, vals):
        logo_data = vals.get('logo')
        if logo_data:
            file_remote_url, serialized_name = self._upload_logo_to_s3(logo_data, vals.get('name', 'brand_logo'))
            vals['logo_url'] = file_remote_url
            vals['logo'] = False  # Remove binary after upload
        return super(ProductBrand, self).create(vals)

    def write(self, vals):
        seo_field = 'seo_keyword_ids'
        seo_changed = False
        old_seos = {}
        if seo_field in vals:
            seo_changed = True
            for brand in self:
                old_seos[brand.id] = set(brand.seo_keyword_ids.ids)

        logo_data = vals.get('logo')
        if logo_data:
            # Delete old logo from S3 if exists
            for rec in self:
                if rec.logo_url:
                    try:
                        old_serialized_name = rec.logo_url.split('/')[-1]
                        S3Service.delete_file(self.env, old_serialized_name)
                        for size_name in IMAGE_SIZES.keys():
                            base_name, ext = FileUtility.extract_extension(old_serialized_name)
                            resized_file_name = f"{base_name}_{size_name}{ext}"
                            if S3Service.check_file_exists(self.env, resized_file_name):
                                S3Service.delete_file(self.env, resized_file_name)
                    except Exception as e:
                        pass  # Optionally log
            file_remote_url, serialized_name = self._upload_logo_to_s3(logo_data)
            vals['logo_url'] = file_remote_url
            vals['logo'] = False

        res = super(ProductBrand, self).write(vals)
        if seo_changed:
            self._propagate_seo_keywords_to_products(old_seos_map=old_seos)
        return res

    def unlink(self):
        for rec in self:
            if rec.logo_url:
                try:
                    serialized_name = rec.logo_url.split('/')[-1]
                    S3Service.delete_file(self.env, serialized_name)
                    for size_name in IMAGE_SIZES.keys():
                        base_name, ext = FileUtility.extract_extension(serialized_name)
                        resized_file_name = f"{base_name}_{size_name}{ext}"
                        if S3Service.check_file_exists(self.env, resized_file_name):
                            S3Service.delete_file(self.env, resized_file_name)
                except Exception as e:
                    pass  # Optionally log
        return super(ProductBrand, self).unlink() 