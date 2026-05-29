# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import UserError
import json
import logging
import base64
import requests as py_requests
from odoo.addons.mataa_advanced_import.services.category_service import CategoryService
from odoo.addons.mataa_advanced_import.services.tag_service import TagService
from odoo.addons.mataa_advanced_import.services.attribute_service import AttributeService
from odoo.addons.mataa_advanced_import.services.product_service import ProductService
from odoo.addons.mataa_advanced_import.services.variant_service import VariantService
from odoo.addons.mataa_advanced_import.services.vendor_service import VendorService
from odoo.addons.mataa_product_management.utility.product_validation_service import ProductValidationService
_logger = logging.getLogger(__name__)
import os


class CreateProductsController(http.Controller):

    def _validate_image_url_extension(self, url):
        file_name = os.path.basename(url.split('?')[0])
        _, ext = os.path.splitext(file_name)
        if not ext:
            raise UserError(
                f"Image URL must include a file extension in its name: {url}"
            )
        return file_name

    def _create_single_product(self, product_data):

        env = request.env

        variants_input = product_data.get('variants', [])
        if not variants_input:
            raise UserError("The 'variants' list is required")

        t_val = {
            'ref': ProductValidationService._validate_template_internal_ref(
                product_data.get('template_internal_ref')
            ),
            'name': ProductValidationService._validate_template_name(
                product_data.get('template_name') if product_data.get('template_name') else product_data.get('template_internal_ref')
            ),
            'brand': ProductValidationService._validate_template_brand(
                product_data.get('template_brand')
            ),
            'cat': ProductValidationService.validate_template_functional_category(
                product_data.get('template_functional_category')
            ),
            'reg_p': ProductValidationService._validate_template_regular_price(
                product_data.get('template_regular_price')
            ),
            'sal_p': ProductValidationService._validate_template_sales_price(
                product_data.get('template_sales_price')
            ),
            'web_cat': ProductValidationService.validate_template_web_categories(
                env,
                product_data.get('template_web_categories')
            ),
            'imgs': ProductValidationService._validate_template_images_url(
                product_data.get('template_images_url') if product_data.get('template_images_url') else []
            ),
            'desc': ProductValidationService._validate_template_description(
                product_data.get('template_Description')
            ),
            'note': ProductValidationService._validate_template_internal_note(
                product_data.get('template_internal_note')
            ),
            'tags': ProductValidationService.validate_template_tags(
                product_data.get('template_tags')
            ),
            'status': ProductValidationService.validate_mataa_status(product_data.get("mataa_status")),
            "last_modified_by": product_data.get("last_modified_by")
        }

        validated_variants = []
        seen_refs = set()

        for v_item in variants_input:
            ref = ProductValidationService._validate_variant_internal_ref(
                v_item.get('variant_internal_ref')
            )

            if ref in seen_refs:
                raise UserError(f"Duplicate SKU '{ref}' in request")

            seen_refs.add(ref)

            if env['product.product'].sudo().with_context(active_test=False).search(
                [('default_code', '=ilike', ref)], limit=1
            ):
                raise UserError(f"SKU '{ref}' already exists")

            validated_variants.append({
                'ref': ref,
                'name': ProductValidationService._validate_variant_name(
                    v_item.get('variant_name') if v_item.get('variant_name') else v_item.get('variant_internal_ref')
                ),
                'price': ProductValidationService._validate_variant_regular_price(
                    v_item.get('variant_regular_price')
                ),
                'barcodes': ProductValidationService._validate_variant_barcodes(
                    v_item.get('variant_barcodes')
                ),
                'attrs': ProductValidationService._validate_variant_attributes(
                    v_item.get('variant_attributes') or v_item.get('attributes')
                ),
                'v_vendor': ProductValidationService._validate_vendor_name(
                    v_item.get('variant_vendor_name')
                ),
                'v_prod_name': ProductValidationService._validate_vendor_product_name(
                    v_item.get('variant_vendor_product_name')
                ),
                'v_price': ProductValidationService._validate_vendor_price(
                    v_item.get('variant_vendor_price')
                ),
                'v_qty': ProductValidationService._validate_vendor_quantity(
                    v_item.get('variant_vendor_quantity')
                ),
                'v_code': ProductValidationService._validate_vendor_product_code(
                    v_item.get('variant_vendor_product_code')
                ),
                'tags': ProductValidationService._validate_variant_tags(
                    v_item.get('variant_tags')
                ),
            'status':ProductValidationService.validate_mataa_status( v_item.get("mataa_status")),

            })
        
        if product_data.get('created_by'):
            created_by = product_data.get('created_by')
        else:
            created_by = "API"

        template = env['product.template'].sudo().create({
            'name': t_val['name'],
            'default_code': t_val['ref'],
            'product_brand_id': t_val['brand'].id if t_val['brand'] else False,
            'categ_id': t_val['cat'].id,
            'regular_price': t_val['reg_p'],
            'list_price': t_val['sal_p'],
            'description': t_val['note'],
            'description_sale': t_val['desc'],
            'type': 'product',
            'mataa_status': t_val['status'],
            'created_by': created_by,
            'last_modified_by': t_val['last_modified_by']
        })

        web_cat = t_val['web_cat']
        if not web_cat:
            web_categories_str = ''
        else:
            if isinstance(web_cat, list):
                web_cat = env['product.public.category'].browse(web_cat)

            web_categories_str = ','.join(web_cat.mapped('name'))
        CategoryService.assign_public_categories(
            env,
            template,
            web_categories_str
        )
        if t_val['tags']:
            TagService.assign_tags(env, template, t_val['tags'])

        new_image_urls = []
        for idx, url in enumerate(t_val['imgs']):
            file_name = self._validate_image_url_extension(url)
            try:
                resp = py_requests.get(url, timeout=30)
                if resp.status_code != 200:
                    raise UserError(f"Failed to download image from URL: {url} (status {resp.status_code})")
            except py_requests.exceptions.RequestException as e:
                raise UserError(f"Failed to download image from URL: {url} - {str(e)}")
            file_data_b64 = base64.b64encode(resp.content).decode('utf-8')

            url_record = env['product.url'].sudo().create({
                'product_tmpl_id': template.id,
                'file_name': file_name,
                'file_data': file_data_b64,
                'sequence': idx,
            })
            new_image_urls.append(url_record.url)

        created_variant_ids = []

        for v in validated_variants:
            attr_value_ids = set()

            for attr_name, attr_val in v['attrs']:
                attribute = AttributeService.get_or_create_attribute(env, attr_name)
                value = AttributeService.get_or_create_attribute_value(
                    env, attribute, attr_val
                )
                ProductService.assign_product_attribute_values(
                    env, template, attribute, value
                )
                attr_value_ids.add(value.id)

            variant = VariantService.update_variant_with_attributes(
                env=env,
                product_template=template,
                variant_name=v['name'],
                internal_ref=v['ref'],
                regular_price=v['price'],
                barcodes=v['barcodes'].split(',') if v['barcodes'] else [],
                attribute_values=attr_value_ids,
                mataa_status=v['status']
            )

            if v['tags']:
                TagService.assign_tags(env, variant, v['tags'])

            VendorService.link_vendor_to_variant(
                env,
                vendor=v['v_vendor'],
                product_variant=variant,
                vendor_product_name=v['v_prod_name'],
                vendor_code=v['v_code'],
                vendor_price=v['v_price'],
                vendor_quantity=v['v_qty']
            )

            created_variant_ids.append(variant.id)

        return {
            "template_id": template.id,
            "variant_ids": created_variant_ids,
            "image_urls": new_image_urls
        }

    @http.route('/mataa_api/product/create', type='http', auth='public', methods=['POST'], csrf=False)
    def create_product(self):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')

        if api_key != expected_api_key:
            return request.make_response(json.dumps({"error": "Unauthorized"}), status=401)

        try:
            payload = json.loads(request.httprequest.data)
            payload = payload.get('params', payload)

            with request.env.cr.savepoint():
                result = self._create_single_product(payload)

            return request.make_response(
                json.dumps({
                    "message": "Success",
                    "template_id": result['template_id'],
                    "variant_ids": result['variant_ids'],
                    "image_urls": result['image_urls']
                }),
                status=200
            )

        except UserError as e:
            return request.make_response(json.dumps({"error": str(e)}), status=400)
        except Exception as e:
            _logger.exception("Create product failed")
            return request.make_response(json.dumps({"error": str(e)}), status=500)

    @http.route('/mataa_api/product/bulk_create', type='http', auth='public', methods=['POST'], csrf=False)
    def bulk_create_products(self):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param(
            'mataa_order_management.api_key'
        )

        if api_key != expected_api_key:
            return request.make_response(json.dumps({"error": "Unauthorized"}), status=401)

        try:
            payload = json.loads(request.httprequest.data)
            payload = payload.get('params', payload)

            products = payload.get('products', [])
            if not products:
                raise UserError("Products list is required")

            results = []
            errors = []

            for index, product_data in enumerate(products):
                try:
                    with request.env.cr.savepoint():
                        result = self._create_single_product(product_data)
                    results.append({
                        "index": index,
                        "template_id": result['template_id'],
                        "variant_ids": result['variant_ids'],
                        "image_urls": result['image_urls'],
                        "status": "success"
                    })
                except UserError as e:
                    errors.append({
                        "index": index,
                        "template_internal_ref": product_data.get('template_internal_ref'),
                        "error": str(e)
                    })
                except Exception:
                    _logger.exception("Bulk product create failed")
                    errors.append({
                        "index": index,
                        "template_internal_ref": product_data.get('template_internal_ref'),
                        "error": "Unexpected server error"
                    })

            return request.make_response(
                json.dumps({
                    "success_count": len(results),
                    "error_count": len(errors),
                    "results": results,
                    "errors": errors
                }),
                status=207 if errors else 200
            )

        except Exception as e:
            _logger.exception("Bulk create fatal error")
            return request.make_response(json.dumps({"error": str(e)}), status=500)

    @http.route('/mataa_api/product/update', type='http', auth='public', methods=['POST'], csrf=False)
    def update_product(self):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param(
            

            'mataa_order_management.api_key'
        )

        if api_key != expected_api_key:
            return request.make_response(
                json.dumps({"error": "Invalid or missing API key"}),
                status=401
            )

        try:
            payload = json.loads(request.httprequest.data)
            payload = payload.get('params', payload)

            with request.env.cr.savepoint():

                template = None
                if payload.get('template_id'):
                    template = request.env['product.template'].sudo().browse(payload['template_id'])
                elif payload.get('template_internal_ref'):
                    template = request.env['product.template'].sudo().search(
                        [('default_code', '=ilike', payload['template_internal_ref'])],
                        limit=1
                    )

                if not template or not template.exists():
                    raise UserError("Product template not found")

                template_vals = {}

                if 'template_internal_ref' in payload:
                    template_vals['default_code'] = (
                        ProductValidationService.validate_template_internal_ref(
                            request.env,
                        payload['template_internal_ref'],
                        exclude_template_id=template.id
                        )
                    )

                if 'template_name' in payload:
                    template_vals['name'] = (
                        ProductValidationService.validate_template_name(
                        payload['template_name']
                        )
                    )

                if 'template_brand' in payload:
                    brand = ProductValidationService._validate_template_brand(payload['template_brand'])
                    if not brand:
                        return request.make_response(json.dumps({"error": "Brand not found"}), status=400)
                    template_vals['product_brand_id'] = brand.id if brand else False

                if 'template_functional_category' in payload:
                    category = ProductValidationService.validate_template_functional_category(payload['template_functional_category'])
                    template_vals['categ_id'] = category.id

                if 'template_regular_price' in payload:
                    template_vals['regular_price'] = payload['template_regular_price']

                if 'template_sales_price' in payload:
                    template_vals['list_price'] = payload['template_sales_price']

                if 'template_internal_note' in payload:
                    template_vals['description'] = payload['template_internal_note']

                if 'template_Description' in payload:
                    template_vals['description_sale'] = payload['template_Description']

                if 'mataa_status' in payload:
                    template_vals['mataa_status'] = (
                        ProductValidationService.validate_mataa_status(
                        payload.get('mataa_status')
                        )
                    )
                
                if 'last_modified_by' in payload:
                    template_vals['last_modified_by'] = payload['last_modified_by']
                else:
                    template_vals['last_modified_by'] = "API"

                if template_vals:
                    template.write(template_vals)

                if 'template_web_categories' in payload:
                    web_categories = ProductValidationService.validate_template_web_categories(
                        request.env,
                        payload.get('template_web_categories')
                    )
                    web_categories_str = ','.join(web_categories.mapped('name')) if web_categories else ''
                    CategoryService.assign_public_categories(
                        request.env,
                        template,
                        web_categories.ids
                    )

                if 'template_tags' in payload:
                    tages_name = {tag.strip() for tag in payload['template_tags'].split(',')}
                    tags = request.env['product.tag'].sudo().search([('name', 'in', list(tages_name))])
                    if len(tags) != len(tages_name):
                        return request.make_response(json.dumps({"error": f"Tag not found: {tages_name - set(tags.mapped('name'))}"}), status=400)
                    TagService.assign_tags(request.env, template, payload['template_tags'])

                if 'product_seo_keywords' in payload:
                    seo_ids = ProductValidationService.validate_product_seo_keywords(
                        request.env,
                        payload.get('product_seo_keywords')
                    )
                    template.write({
                        'product_seo_keywords': [(6, 0, seo_ids or [])]
                    })

                new_image_urls = []
                if 'template_images_url' in payload:
                    urls = ProductValidationService._validate_template_images_url(
                        payload.get('template_images_url')
                    )
                    if urls and len(urls) != len(set(urls)):
                        raise UserError(f"Duplicate image URLs:")

                    existing_by_url = {rec.url: rec for rec in template.image_url_ids if rec.url}

                    deleted_urls = []
                    for rec in template.image_url_ids:
                        if rec.url not in urls:
                            deleted_urls.append(rec)

                    for idx, url in enumerate(urls or []):
                        if url in existing_by_url:
                            existing_by_url[url].sudo().write({'sequence': idx})
                            new_image_urls.append(existing_by_url[url].url)
                        else:
                            try:
                                resp = py_requests.get(url, timeout=30)
                                if resp.status_code != 200:
                                    raise UserError(f"Failed to download image from URL: {url} (status {resp.status_code})")
                            except py_requests.exceptions.RequestException as e:
                                raise UserError(f"Failed to download image from URL: {url} - {str(e)}")

                            file_name = self._validate_image_url_extension(url)
                            file_data_b64 = base64.b64encode(resp.content).decode('utf-8')

                            url_record = request.env['product.url'].sudo().create({
                                'product_tmpl_id': template.id,
                                'file_name': file_name,
                                'file_data': file_data_b64,
                                'sequence': idx,
                            })
                            new_image_urls.append(url_record.url)
                    
                    for rec in deleted_urls:
                        rec.sudo().unlink()
    
                    template._get_main_image()      


                variants = payload.get('variants', [])
                errors = []
                for v in variants:
                    try:
                        single_variant = len(template.product_variant_ids) == 1

                        if single_variant:
                            variant = template.product_variant_ids[0]

                        else:
                            variant_id = v.get('variant_id')
                            variant_ref = (v.get('variant_internal_ref') or '').strip()

                            if variant_id:
                                variant = request.env['product.product'].sudo().browse(variant_id)

                            elif variant_ref:
                                variant = request.env['product.product'].sudo().search([
                                    ('default_code', '=', variant_ref),
                                ], limit=1)
                            else:
                                raise UserError(
                                    "Each variant must have 'variant_id' or 'variant_internal_ref'"
                                )
                        if not variant or not variant.exists():
                            raise UserError(f"Variant not found for ID '{v.get('variant_id')}' or SKU '{v.get('variant_internal_ref')}'")

                        variant_vals = {}

                        if 'variant_internal_ref' in v:
                            variant_vals['default_code'] = (
                                ProductValidationService.validate_variant_internal_ref(
                                    request.env,
                                v['variant_internal_ref'],
                                exclude_variant_id=variant.id
                                )
                            )

                        if 'variant_name' in v:
                            variant_vals['name'] = (
                                ProductValidationService._validate_variant_name(
                                v['variant_name']
                                )
                            )

                        if 'variant_regular_price' in v:
                            variant_vals['regular_price'] = (
                                ProductValidationService.validate_variant_price(
                                v['variant_regular_price']
                                )
                            )

                        if variant_vals:
                            variant.write(variant_vals)

                        if 'variant_attributes' in v:
                            attrs = ProductValidationService._validate_variant_attributes(
                                v['variant_attributes']
                            )

                            attr_value_ids = set()
                            for attr_name, attr_val in attrs:
                                attribute = AttributeService.get_or_create_attribute(request.env, attr_name)
                                value = AttributeService.get_or_create_attribute_value(
                                    request.env, attribute, attr_val
                                )
                                attr_value_ids.add(value.id)

                            VariantService.update_variant_with_attributes(
                                env=request.env,
                                product_template=template,
                                variant_name=variant.name,
                                internal_ref=variant.default_code,
                                regular_price=variant.regular_price,
                                barcodes=[variant.barcode] if variant.barcode else [],
                                attribute_values=attr_value_ids
                            )

                        if 'variant_barcodes' in v:
                            variant.barcode = v['variant_barcodes']

                        if 'variant_tags' in v:
                            TagService.assign_tags(request.env, variant, v['variant_tags'])

                        if 'mataa_status' in v:
                            variant.write({
                                'mataa_status': ProductValidationService.validate_mataa_status(
                                    v.get('mataa_status')
                                )
                            })

                        if 'variant_vendor_name' in v:
                            vendor = ProductValidationService._validate_vendor_name(
                                v['variant_vendor_name']
                            )

                            VendorService.link_vendor_to_variant(
                                request.env,
                                vendor=vendor,
                                product_variant=variant,
                                vendor_product_name=v.get('variant_vendor_product_name'),
                                vendor_code=v.get('variant_vendor_product_code'),
                                vendor_price=v.get('variant_vendor_price'),
                                vendor_quantity=v.get('variant_vendor_quantity')
                            )
                    except Exception as e:
                        errors.append(f"Variant {v.get('variant_internal_ref')} update failed: {str(e)}")
                        continue

                if 0 < len(errors):
                    return request.make_response(
                        json.dumps({
                            "message": "Product updated with error/s",
                            "template_id": template.id,
                            "image_urls": new_image_urls,
                            "errors": errors
                        }),
                        status=400
                    )
                return request.make_response(
                    json.dumps({
                        "message": "Product updated successfully",
                        "template_id": template.id,
                        "image_urls": new_image_urls,
                    }),
                    status=200
                )

        except UserError as e:
            _logger.warning("Product update failed: %s", e)
            return request.make_response(
                json.dumps({"error": str(e)}),
                status=400
            )

        except Exception as e:
            _logger.exception("Unexpected error during product update")
            return request.make_response(
                json.dumps({"error": str(e)}),
                status=500
            )

    @http.route('/mataa_api/product/sync', type='http', auth='public', methods=['POST'], csrf=False)
    def sync_product(self):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param(
            'mataa_order_management.api_key'
        )

        if api_key != expected_api_key:
            return request.make_response(
                json.dumps({"error": "Invalid or missing API key"}),
                status=401
            )

        try:
            payload = json.loads(request.httprequest.data)
            payload = payload.get('params', payload)

            env = request.env

            template = None
            if payload.get('template_id'):
                template = env['product.template'].sudo().browse(payload['template_id'])
            elif payload.get('template_internal_ref'):
                template = env['product.template'].sudo().search(
                    [('default_code', '=', payload['template_internal_ref'])],
                    limit=1
                )

            if not template or not template.exists():
                raise UserError("Product template not found")

            if template.check_product_restriction():
                raise UserError(
                    f"Product '{template.default_code}' has restricted tags. Sync prevented."
                )

            if not template.mataa_id:
                template.create_on_external()
                action = 'created'
            else:
                template.update_on_external()
                template.product_variant_ids.sync_variants()
                action = 'updated'

            return request.make_response(
                json.dumps({
                    "message": f"Product synced successfully ({action})",
                    "template_id": template.id,
                    "mataa_id": template.mataa_id,
                    "sync_status": template.sync_status
                }),
                headers=[('Content-Type', 'application/json')],
                status=200
            )

        except UserError as e:
            _logger.warning("Product sync failed: %s", e)
            return request.make_response(
                json.dumps({"error": str(e)}),
                status=400
            )

        except Exception as e:
            _logger.exception("Unexpected error during product sync")
            return request.make_response(
                json.dumps({"error": str(e)}),
                status=500
            )

    @http.route('/mataa_api/product/functional_categories',type='http',auth='public',methods=['GET'],csrf=False)
    def get_functional_categories(self):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')

        if api_key != expected_api_key:
            return request.make_response(
                json.dumps({"error": "Invalid or missing API key"}),
                status=401,
                headers=[('Content-Type', 'application/json')]
            )

        try:
            env = request.env
            categories = env['product.category'].sudo().search([], order='parent_id, name')

            result = []
            for cat in categories:
                result.append({
                    "id": cat.id,
                    "name": cat.name,
                    "parent_id": cat.parent_id.id if cat.parent_id else None,
                    "parent_name": cat.parent_id.name if cat.parent_id else None,
                    "complete_name": cat.complete_name
                })

            return request.make_response(
                json.dumps({
                    "count": len(result),
                    "categories": result
                }),
                status=200,
                headers=[('Content-Type', 'application/json')]
            )

        except Exception as e:
            _logger.exception("Failed to fetch functional categories")
            return request.make_response(
                json.dumps({"error": str(e)}),
                status=500,
                headers=[('Content-Type', 'application/json')]
            )
