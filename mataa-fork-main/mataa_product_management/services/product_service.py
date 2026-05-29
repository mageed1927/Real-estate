# services/product_service.py
from odoo.http import request


class ProductService:
    @staticmethod
    def get_quantities_by_mataa_ids(mataa_ids):
        if not mataa_ids:
            return []


        products = request.env['product.product'].sudo().search_read(
            [('id', 'in', mataa_ids)],
            ['id', 'draft_reserved_qty']
        )
        if not products:
            return []

        product_map = {p['id']: p['id'] for p in products}
        draft_reserved_map = {p['id']: p['draft_reserved_qty'] for p in products}

        product_ids = list(product_map.keys())


        location_ids = request.env.company.sudo().mataa_in_stock_locations_ids

        quant_groups = request.env['stock.quant'].sudo().read_group(
            domain=[('product_id', 'in', product_ids), ('location_id', 'in', location_ids.ids)],
            fields=['quantity:sum', 'reserved_quantity:sum'],
            groupby=['product_id']
        )
        free_qty_map = {
            group['product_id'][0]: group.get('quantity', 0) - group.get('reserved_quantity', 0)
            for group in quant_groups
        }

        supplier_groups = request.env['product.supplierinfo'].sudo().read_group(
            domain=[('product_id', 'in', product_ids), ('published', '=', True)],
            fields=['min_qty:sum'],
            groupby=['product_id']
        )
        supplier_qty_map = {
            group['product_id'][0]: group.get('min_qty', 0)
            for group in supplier_groups
        }

        response_data = []
        for pid, mid in product_map.items():
            free_qty = free_qty_map.get(pid, 0.0)
            draft_reserved = draft_reserved_map.get(pid, 0.0)
            supplier_qty = supplier_qty_map.get(pid, 0.0)

            total_quantity = free_qty - draft_reserved + supplier_qty

            response_data.append({'mataa_id': mid, 'Quantity': total_quantity})

        return response_data
    
    @staticmethod
    def get_product_template_info(self, product_id):
        product = request.env['product.template'].sudo().browse(int(product_id))
        
        if not product.exists():
            return None

        images = request.env['product.url'].sudo().search([
            ('product_tmpl_id', '=', product.id)
        ], order='sequence asc')

        variants_list = []
        for variant in product.product_variant_ids:

            variant_data = ProductService.get_product_variant_info(self, variant.id)
            variants_list.append(variant_data)

        return {
            'id': product.id,
            'template_internal_ref': product.default_code,
            'template_name': product.name,
            'template_brand': product.product_brand_id.name if product.product_brand_id else False,
            'template_functional_category': product.categ_id.name,

            'template_regular_price': product.regular_price,
            'template_sales_price': product.list_price,

            'template_web_categories': product.public_categ_ids.ids,
            'template_images_url': images.mapped('url'),
            'template_tags': product.product_tag_ids.ids,

            'template_Description': product.description_sale,
            'template_internal_note': product.description,

            'variants': variants_list
        }

    @staticmethod
    def get_product_variant_info(self, variant_id):
        variant = request.env['product.product'].sudo().browse(int(variant_id))
        
        if not variant.exists():
            return None

        vendors = []
        sellers = [seller for seller in variant.seller_ids if seller.product_id.id == variant.id]
        
        if sellers:
            for seller in sellers:
                vendor_info = {
                    'variant_vendor_name': seller.partner_id.name,
                    'variant_vendor_product_name': seller.product_name,
                    'variant_vendor_product_code': seller.product_code,
                    'variant_vendor_price': seller.price,
                    'variant_vendor_quantity': seller.min_qty,
                }
                vendors.append(vendor_info)

        quant = request.env['stock.quant'].sudo().search([
            ('product_id', '=', variant.id),
            ('location_id.usage', '=', "internal")
        ])
        variant_location = [
            {
                'location': q.location_id.complete_name if q.location_id else False,
                'package': q.package_id.name if q.package_id else False,
                'quantity': q.quantity,
            }
            for q in quant
        ]

        return {
            'variant_id': variant.id,
            'template_id': variant.product_tmpl_id.id,
            'variant_mataa_id': variant.mataa_id,

            'variant_internal_ref': variant.default_code,
            'variant_name': variant.name,
            'variant_location': variant_location,

            'variant_sales_price': variant.lst_price, 
            'variant_regular_price': variant.regular_price,
            
            'variant_barcodes': variant.barcode or '',
            'variant_attributes': variant.product_template_attribute_value_ids.ids,
            'variant_tags': variant.product_tag_ids.ids,

            'variant_description': variant.description_sale,
            'variant_is_on_stock': variant.get_mataa_quantity() > 0,
            'vendors':vendors
        }
    
    @staticmethod
    def get_product_variant_info_by_barcode(self, barcode):
        variant = request.env['product.product'].sudo().search([
            ('barcode', '=', barcode)
        ], limit=1)

        if not variant:
            return None

        vendors = []
        sellers = [seller for seller in variant.seller_ids if seller.product_id.id == variant.id]
        
        if sellers:
            for seller in sellers:
                vendor_info = {
                    'variant_vendor_name': seller.partner_id.name,
                    'variant_vendor_product_name': seller.product_name,
                    'variant_vendor_product_code': seller.product_code,
                    'variant_vendor_price': seller.price,
                    'variant_vendor_quantity': seller.min_qty,
                }
                vendors.append(vendor_info)

        quant = request.env['stock.quant'].sudo().search([
            ('product_id', '=', variant.id),
            ('location_id.usage', '=', "internal")
        ])
        variant_location = [
            {
                'location': q.location_id.complete_name if q.location_id else None,
                'package': q.package_id.name if q.package_id else None,
                'quantity': q.quantity,
            }
            for q in quant
        ]

        product_template = variant.product_tmpl_id

        return {
            'template_id': product_template.id,
            'template_internal_ref': product_template.default_code,
            'template_name': product_template.name,
            'template_brand': product_template.product_brand_id.name if product_template.product_brand_id else None,
            'template_functional_category': product_template.categ_id.name if product_template.categ_id else None,

            'template_regular_price': product_template.regular_price,
            'template_sales_price': product_template.list_price,

            'template_web_categories': [{p.id:p.display_name} for p in product_template.public_categ_ids],
            'template_images_url': product_template.image_url_ids.mapped('url'),
            'template_tags': [p.name for p in product_template.product_tag_ids],

            'template_Description': product_template.description_sale,
            'template_internal_note': product_template.description,

            'variant_id': variant.id,
            'variant_mataa_id': variant.mataa_id,

            'variant_internal_ref': variant.default_code,
            'variant_name': variant.name,
            'variant_location': variant_location,

            'variant_sales_price': variant.lst_price, 
            'variant_regular_price': variant.regular_price,
            
            'variant_barcodes': variant.barcode,
            'variant_attributes': [{v.attribute_id.name: v.name} for v in variant.product_template_attribute_value_ids],
            'variant_tags': [v.name for v in variant.product_tag_ids],

            'variant_description': variant.description_sale,
            'variant_is_on_stock': variant.get_mataa_quantity() > 0,
            'vendors':vendors
        }