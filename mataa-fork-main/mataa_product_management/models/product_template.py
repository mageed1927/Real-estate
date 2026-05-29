# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
import requests
from ..utility.external_api_utility import ExternalAuthUtil
from ..constants.extenal_api_config import ExternalApiConfig
from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Override the default value for the product type field to be "Storable Product"
    detailed_type = fields.Selection([
            ('consu', 'Consumable'),
            ('service', 'Service'),
            ('product', 'Storable Product')
        ],
        string='Product Type',
        default='product'
    )

    created_by = fields.Char(string='Created By', store=True)
    last_modified_by = fields.Char(string='Last Modified By', store=True) 
    last_modified_date = fields.Datetime(string='Last Modified Date', store=True)

    name = fields.Char(tracking=True)

    product_brand_id = fields.Many2one(tracking=True)
    
    description_sale = fields.Text(tracking=True)

    default_code = fields.Char('Internal Reference', compute=False, store=True,tracking=True, inverse=False)

    regular_price = fields.Float(string="Regular Price", default=1.0, digits='Regular Price', tracking=True)
    list_price = fields.Float(tracking=True)

    image_url_ids = fields.One2many(string="Images", comodel_name="product.url", inverse_name="product_tmpl_id",
                                    ondelete='cascade')
    main_image = fields.Char(string='Main image', help='Get first image from table images', compute="_get_main_image",
                             store=True)

    last_leaf_category = fields.Char(string='Last Leaf Category', compute='_compute_last_leaf_category')

    product_seo_keywords = fields.Many2many(
        'product.seo.keyword',
        string='SEO Keywords',
        help="SEO keywords for the product to improve SEO."
    )

    restricted_seo_keyword_ids = fields.Many2many(
        'product.seo.keyword',
        'product_template_restricted_seo_rel',
        'product_tmpl_id',
        'seo_id',
        string='Restricted SEO Keywords',
        help='SEO keywords that should NOT be propagated from categories to this product.'
    )

    offer_tag_ids = fields.Many2many(
        'product.offer.tag',
        string='Offer Tags',
        help="Offer tags for the product."
    )

    active = fields.Boolean(tracking=True)

    is_price_manager = fields.Boolean(compute='_compute_is_price_manager')

    barcode = fields.Char(tracking=True)

    def _compute_is_price_manager(self):
        for record in self:
            record.is_price_manager = self.env.user.has_group('__custom__.group_sales_change_prices')

    @api.depends('image_url_ids')
    def _get_main_image(self):
        for record in self:
            record.main_image = record.image_url_ids.sorted('sequence')[0].url if record.image_url_ids else False
    
    @api.depends('public_categ_ids')
    def _compute_last_leaf_category(self):
        for record in self:
            last_leaf_categ_id = record.public_categ_ids.sorted(key=lambda c: len(str(c.parent_path).split('/')))[-1].id if record.public_categ_ids else None
            record.last_leaf_category = record.public_categ_ids.browse(last_leaf_categ_id).name.split('/')[-1] if last_leaf_categ_id else None

    @api.constrains('default_code')
    def _check_unique_default_code(self):
        for record in self:
            if record.default_code:
                # Search for other products with the same default_code
                existing_product = self.search([('default_code', '=ilike', record.default_code), ('id', '!=', record.id)])
                if existing_product:
                    raise UserError(
                        f"The following internal reference: {record.default_code} was found in other products. \n"
                        "Note that product internal references should not repeat."
                    )

    @api.constrains('regular_price', 'list_price')
    def _check_regular_vs_list_price(self):
        for record in self:
            if record.list_price:
                if record.detailed_type == "product" and record.regular_price < record.list_price:
                    raise UserError("Regular price must be larger than sale price.")

    @api.constrains('regular_price', 'list_price')
    def _check_vendor_vs_regular_vs_sale_price(self):
        for record in self:
            if len(record.product_variant_ids) > 1:
                continue

            domain = [('product_tmpl_id', '=', record.id)]
            if self.env.context.get('skip_vendor_price_check', False):
                return
            self._validate_vendor_prices(self.env['product.supplierinfo'].search(domain), record)

    def _validate_vendor_prices(self, vendor_infos, product):
        prices_control = self.env['ir.config_parameter'].sudo().get_param('mataa_order_management.prices_control')
        for vendor_info in vendor_infos:
            vendor_price = vendor_info._get_converted_price(vendor_info)
            if bool(prices_control) and vendor_price > min(product.list_price, product.regular_price):
                vendor_info._raise_invalid_price_error(vendor_info, product, vendor_price)

    def _propagate_seo_keywords_on_category_change(self, old_categs_map=None, force=False):
        product_add_map = {}
        # product_remove_map = {}  # No longer used for force
        for product in self:
            new_categs = set(product.public_categ_ids.ids)
            old = set() if old_categs_map is None else old_categs_map.get(product.id, set())
            added = new_categs - old
            removed = old - new_categs
            # Handle added categories or force
            if added or force:
                # If force, recalculate all category SEOs
                if force:
                    all_cat_seos = set()
                    for cat in product.public_categ_ids:
                        all_cat_seos |= set(cat.seo_keyword_ids.ids)
                    # Remove restricted
                    to_add = set(all_cat_seos) - set(product.product_seo_keywords.ids) - set(product.restricted_seo_keyword_ids.ids)
                    if to_add:
                        product_add_map.setdefault(product.id, set()).update(to_add)
                else:
                    for cat_id in added:
                        cat = self.env['product.public.category'].browse(cat_id)
                        cat_seos = set(cat.seo_keyword_ids.ids)
                        to_add = set(cat_seos - set(product.product_seo_keywords.ids) - set(product.restricted_seo_keyword_ids.ids))
                        if to_add:
                            product_add_map.setdefault(product.id, set()).update(to_add)
            # Handle removed categories (only for normal propagation, not force)
            if removed and not force:
                for cat_id in removed:
                    cat = self.env['product.public.category'].browse(cat_id)
                    cat_seos = set(cat.seo_keyword_ids.ids)
                    for seo_id in cat_seos:
                        other_categs = product.public_categ_ids.filtered(lambda c: c.id != cat_id)
                        other_seos = set()
                        for other_cat in other_categs:
                            other_seos |= set(other_cat.seo_keyword_ids.ids)
                        if seo_id not in other_seos:
                            product._remove_seo_keywords([seo_id])
        for product_id, add_ids in product_add_map.items():
            if add_ids:
                self.env['product.template'].browse(product_id).write({'product_seo_keywords': [(4, seo_id) for seo_id in add_ids]})

    def force_propagate_seo_keywords(self):
        self._propagate_seo_keywords_on_category_change(force=True)

    def _add_seo_keywords(self, seo_ids):
        if seo_ids:
            self.write({'product_seo_keywords': [(4, seo_id) for seo_id in seo_ids]})

    def _remove_seo_keywords(self, seo_ids):
        if seo_ids:
            self.write({'product_seo_keywords': [(3, seo_id) for seo_id in seo_ids]})

    def _get_brand_field_on_product(self):
        return 'product_brand_id' if 'product_brand_id' in self._fields else 'brand_id'

    def _propagate_brand_seo_on_brand_change(self, old_brand_map=None):
        for product in self:
            brand_field = self._get_brand_field_on_product()
            new_brand = getattr(product, brand_field)
            old_brand_id = None if old_brand_map is None else old_brand_map.get(product.id)

            if new_brand and (old_brand_id != new_brand.id):
                brand_seos = set(new_brand.seo_keyword_ids.ids)
                existing = set(product.product_seo_keywords.ids)
                restricted = set(product.restricted_seo_keyword_ids.ids)
                to_add = brand_seos - existing - restricted
                if to_add:
                    product.write({'product_seo_keywords': [(4, sid) for sid in to_add]})
            # removals (only if no category still provides it and not in new brand)
            if old_brand_id and (not new_brand or new_brand.id != old_brand_id):
                old_brand = self.env['product.brand'].browse(old_brand_id)
                removed = set(old_brand.seo_keyword_ids.ids)
                cat_seos = set()
                for c in product.public_categ_ids:
                    cat_seos |= set(c.seo_keyword_ids.ids)
                keep = cat_seos | (set(new_brand.seo_keyword_ids.ids) if new_brand else set())
                to_remove = removed - keep
                if to_remove:
                    product.write({'product_seo_keywords': [(3, sid) for sid in to_remove]})

    def write(self, vals):
        if 'active' in vals:
            self._check_archive_permission_on_active_change(vals.get('active'))
        
        if 'last_modified_by'in vals:
            vals['last_modified_date'] = fields.Datetime.now()
        _logger.info(f"product {self.ids} updated by {vals.get('last_modified_by', 'N/A')}")
        _logger.info(f"product {self.ids} updated by user: {self.env.user.id or 'N/A'}")

        # Intercept manual removal of SEO keywords and add to restricted list
        if 'product_seo_keywords' in vals:
            removed_seos = set()
            if isinstance(vals['product_seo_keywords'], list):
                for op in vals['product_seo_keywords']:
                    if isinstance(op, (list, tuple)) and op[0] == 3:
                        removed_seos.add(op[1])
            if removed_seos:
                for product in self:
                    current_restricted = set(product.restricted_seo_keyword_ids.ids)
                    to_add = removed_seos - current_restricted
                    if to_add:
                        product.restricted_seo_keyword_ids = [(4, seo_id) for seo_id in to_add]
        categ_changed = False
        old_categs = {}

        if 'public_categ_ids' in vals:
            categ_changed = True
            for product in self:
                old_categs[product.id] = set(product.public_categ_ids.ids)

            final_categories = self.env['product.public.category']
            commands = vals.get('public_categ_ids', [])
            has_replace = any(cmd[0] == 6 for cmd in commands)

            if has_replace:
                for cmd in commands:
                    if cmd[0] == 6:
                        final_categories = self.env['product.public.category'].browse(cmd[2])
            else:
                final_categories = self.public_categ_ids
                for cmd in commands:
                    if cmd[0] == 4:
                        final_categories |= self.env['product.public.category'].browse(cmd[1])
                    elif cmd[0] == 3:
                        final_categories -= self.env['product.public.category'].browse(cmd[1])

            expanded_categories = self._expand_public_categories_with_parents(final_categories)
            vals['public_categ_ids'] = [(6, 0, expanded_categories.ids)]

        brand_field = self._get_brand_field_on_product()
        brand_changed = brand_field in vals
        old_brand = {}
        if brand_changed:
            for p in self:
                old_brand[p.id] = getattr(p, brand_field).id or False
        res = super(ProductTemplate, self).write(vals)
        if brand_changed:
            self._propagate_brand_seo_on_brand_change(old_brand_map=old_brand)
        if categ_changed:
            self._propagate_seo_keywords_on_category_change(old_categs_map=old_categs)
        return res

    @api.model
    def create(self, vals):

        if not vals.get('created_by'):
            vals['created_by'] = self.env.user.name or 'N/A'
        if not vals.get('last_modified_by'):
            vals['last_modified_by'] = self.env.user.name or 'N/A'
        vals['last_modified_date'] = fields.Datetime.now()
        
        _logger.info(f"product {vals.get('default_code', 'N/A')} created by {vals.get('created_by', 'N/A')}")
        if vals.get('public_categ_ids'):
            categories = self.env['product.public.category']

            for cmd in vals['public_categ_ids']:
                if cmd[0] == 6:
                    categories = self.env['product.public.category'].browse(cmd[2])
                elif cmd[0] == 4:
                    categories |= self.env['product.public.category'].browse(cmd[1])

            expanded = self._expand_public_categories_with_parents(categories)
            vals['public_categ_ids'] = [(6, 0, expanded.ids)]

        return super(ProductTemplate, self).create(vals)

    is_discounted = fields.Boolean(
        string="Is Discounted",
        compute='_compute_is_discounted',
        store=True
    )

    @api.depends('list_price', 'regular_price')
    def _compute_is_discounted(self):
        for product in self:
            if product.regular_price and product.list_price:
                product.is_discounted = product.list_price < product.regular_price
            else:
                product.is_discounted = False

    has_leaf_public_category = fields.Boolean(
        string="Has Leaf eCommerce Category",
        compute="_compute_has_leaf_public_category",
        store=True,
        help="True if the product belongs to at least one eCommerce category that has no children."
    )

    @api.depends('public_categ_ids', 'public_categ_ids.child_id')
    def _compute_has_leaf_public_category(self):
        for product in self:
            has_leaf = False
            if product.public_categ_ids:
                for category in product.public_categ_ids:
                    if not category.child_id:
                        has_leaf = True
                        break
            product.has_leaf_public_category = has_leaf

    @api.model
    def _expand_public_categories_with_parents(self, categories):
        """
        Return categories + all their parents up to the root.
        """
        result = self.env['product.public.category']
        for category in categories:
            current = category
            while current:
                result |= current
                current = current.parent_id
        return result

    def _check_archive_permission_on_active_change(self, target_active):
        if self.env.su:
            return
        target_active = bool(target_active)
        if target_active is False and any(product.active for product in self):
            if self.env.user.has_group('mataa_product_management.group_product_archive_manager'):
                return
            raise UserError(_("عذراً، لا تمتلك الصلاحيات الكافية لأرشفة هذا المنتج."))
        if target_active is True and any(not product.active for product in self):
            if self.env.user.has_group('mataa_product_management.group_product_unarchive_manager'):
                return
            raise UserError(_("عذراً، لا تمتلك الصلاحيات الكافية لفك أرشفة هذا المنتج."))
    
    def action_archive(self):
        self._check_archive_permission_on_active_change(False)
        # send Ems to archive 
        for product in self:
            url = f"{ExternalApiConfig.get_external_api_catalog_management_url()}/api/v1/Product/Archive/{product.id}"
            response = requests.put(url, headers=ExternalAuthUtil.get_auth_headers(), verify=False)
            if response.status_code != 204:
                # raise error message 
                ExternalAuthUtil.get_error_arhive(response)
        return super(ProductTemplate, self).action_archive()


    def action_unarchive(self):
        self._check_archive_permission_on_active_change(True)
        # send Ems to archive 
        for product in self:
            url = f"{ExternalApiConfig.get_external_api_catalog_management_url()}/api/v1/Product/UnArchive/{product.id}"
            response = requests.put(url, headers=ExternalAuthUtil.get_auth_headers(), verify=False)
            if response.status_code != 204:
                # raise error message 
                ExternalAuthUtil.get_error_arhive(response)
        return super(ProductTemplate, self).action_unarchive()
