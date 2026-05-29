# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class ManageProductsController(http.Controller):

    @http.route('/mataa_api/product/check_existence', type='http', auth='public', methods=['POST'], csrf=False)
    def check_existence(self):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return request.make_response(
                json.dumps({"error": "Invalid or missing API key."}),
                headers=[('Content-Type', 'application/json')],
                status=401
            )
        
        try:
            data = json.loads(request.httprequest.data)
            params = data.get('params', data)  # Support both formats
            default_codes = params.get('default_code', [])
            barcodes = params.get('barcodes', [])
            
            default_codes = [dc for dc in (default_codes or []) if dc and str(dc).strip()]
            barcodes = [barcode for barcode in (barcodes or []) if barcode and str(barcode).strip()]
            
            Product = request.env['product.product'].sudo()
            result = {
                "default_code": {},
                "barcodes": {}
            }
            
            # Using case-insensitive search
            if default_codes:
                _logger.info(f"Checking existence for {len(default_codes)} default_code(s) (Internal Reference)")
                for default_code in default_codes:
                    dc_str = str(default_code).strip()
                    _logger.info(f"Searching for default_code: '{dc_str}' (length: {len(dc_str)}, type: {type(dc_str)})")
                    

                    product = Product.with_context(active_test=False).search(
                        [('default_code', '=ilike', dc_str)],
                        limit=1
                    )
                    
                    exists = bool(product)
                    if exists:
                        _logger.info(f"✓ Found product ID {product.id} with default_code: '{product.default_code}'")
                    else:
                        _logger.warning(f"✗ No product found for default_code: '{dc_str}'")
                        sample_products = Product.with_context(active_test=False).search_read(
                            [('default_code', '!=', False)],
                            ['default_code'],
                            limit=3
                        )
                        if sample_products:
                            sample_codes = [p.get('default_code') for p in sample_products if p.get('default_code')]
                            _logger.debug(f"Sample existing default_codes in DB: {sample_codes}")
                    
                    result["default_code"][default_code] = "exists" if exists else "not_exists"
                    _logger.info(f"Result for default_code '{default_code}': {'EXISTS' if exists else 'NOT EXISTS'}")
            
            # Check barcodes
            if barcodes:
                _logger.info(f"Checking existence for {len(barcodes)} barcode(s)")
                # Search for each barcode individually
                for barcode in barcodes:
                    barcode_str = str(barcode).strip()
                    # Search for product with this exact barcode
                    product = Product.with_context(active_test=False).search(
                        [('barcode', '=', barcode_str)],
                        limit=1
                    )
                    exists = bool(product)
                    result["barcodes"][barcode] = "exists" if exists else "not_exists"
                    _logger.info(f"Barcode '{barcode}': {'EXISTS' if exists else 'NOT EXISTS'}")
            
            return request.make_response(
                json.dumps(result),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            _logger.error("Error checking existence: %s", str(e))
            return request.make_response(
                json.dumps({"error": str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500
            )

    @http.route('/mataa_api/product/create_purchase_order', type='http', auth='public', methods=['POST'], csrf=False)
    def create_purchase_order(self):

        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return request.make_response(
                json.dumps({"error": "Invalid or missing API key."}),
                headers=[('Content-Type', 'application/json')],
                status=401
            )
        
        try:
            data = json.loads(request.httprequest.data)
            _logger.info(f"Received create purchase order request: {json.dumps(data)}")

            params = data.get('params', data)
            order_data = params.get('order_data', params)
            
            _logger.info(f"Extracted order_data: {json.dumps(order_data)}")
            
            PurchaseOrder = request.env['purchase.order'].sudo()
            PurchaseOrderLine = request.env['purchase.order.line'].sudo()
            
            # Validate required fields
            partner_id = order_data.get('partner_id')
            if partner_id is None or partner_id == '' or partner_id == 0:
                _logger.error(f"partner_id is missing or invalid. Received: {partner_id}, order_data keys: {list(order_data.keys()) if isinstance(order_data, dict) else 'not a dict'}")
                return request.make_response(
                    json.dumps({
                        "error": "partner_id is required",
                        "hint": "Expected format: {\"params\": {\"order_data\": {\"partner_id\": 1, \"order_line\": [...]}}} or {\"partner_id\": 1, \"order_line\": [...]}"
                    }),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )
            picking_type_id = order_data.get('picking_type_id')

            if picking_type_id:
                picking_type = request.env['stock.picking.type'].sudo().search(
                    [('id', '=', picking_type_id), ('code', '=', 'incoming')],
                    limit=1
                )
                if not picking_type:
                    return request.make_response(
                        json.dumps({"error": f"Invalid picking_type_id: {picking_type_id}"}),
                        headers=[('Content-Type', 'application/json')],
                        status=400
                    )
            else:
                picking_type = None
            if not order_data.get('order_line'):
                return request.make_response(
                    json.dumps({"error": "order_line is required and must not be empty"}),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )
            
            # Prepare purchase order values
            po_vals = {
                'partner_id': partner_id,
            }
            if picking_type:
                po_vals['picking_type_id'] = picking_type.id
            _logger.info(f"Creating purchase order with partner_id={partner_id}")

            # The order is created first, then sync happens, even if sync fails, order exists
            sync_error = None
            purchase_order = None
            try:
                purchase_order = PurchaseOrder.create(po_vals)
                _logger.info(f"Created purchase order ID {purchase_order.id}")
            except UserError as e:
                error_message = str(e)
                # Extract order ID from error message if available
                order_id = None
                if 'Order ID:' in error_message:
                    try:
                        order_id = int(error_message.split('Order ID:')[1].strip().split()[0])
                        # order was created
                        purchase_order = PurchaseOrder.browse(order_id)
                        if purchase_order.exists():
                            sync_error = error_message
                            _logger.warning(f"Purchase order {order_id} created but VMS sync failed: {error_message}")
                        else:
                            # Order doesn't exist
                            raise
                    except (ValueError, IndexError):
                        raise
                else:
                    raise
            
            # Validate all order lines first before creating any
            errors = []
            validated_lines = []
            
            _logger.info(f"Validating {len(order_data['order_line'])} order line(s)")
            
            for idx, line_data in enumerate(order_data['order_line']):
                line_errors = []
                
                if not line_data.get('product_id'):
                    line_errors.append("product_id is required")
                else:
                    product_id = line_data.get('product_id')
                    # Validate that product exists using search
                    Product = request.env['product.product'].sudo()
                    # Search with active_test=False
                    product = Product.with_context(active_test=False).search([('id', '=', product_id)], limit=1)
                    
                    if not product:
                        # Try to see if it's a template ID instead
                        template = request.env['product.template'].sudo().with_context(active_test=False).search(
                            [('id', '=', product_id)], limit=1
                        )
                        if template and template.product_variant_ids:
                            # Use the first variant if it's a template
                            product = template.product_variant_ids[0]
                            _logger.info(f"Product ID {product_id} is a template, using first variant ID {product.id}")
                        else:
                            # Product truly doesn't exist
                            _logger.error(f"Product ID {product_id} not found (neither product nor template)")
                            line_errors.append(f"Product ID {product_id} does not exist or has been deleted")
                            continue
                    

                    if hasattr(product, 'purchase_ok') and not product.purchase_ok:
                        _logger.warning(f"Product ID {product_id} is not purchaseable (purchase_ok=False)")

                    
                    line_data['_validated_product'] = product
                    line_data['_product_id'] = product.id  # Use the actual product ID
                    _logger.info(f"Product ID {product.id} (name: {product.name}, default_code: {product.default_code or 'N/A'}) validated successfully for order line {idx + 1}")
                
                if not line_data.get('product_qty'):
                    line_errors.append("product_qty is required")
                
                # Validate package_name if provided
                packeg_name = line_data.get('packeg_name') or line_data.get('package_name')
                if packeg_name:
                    package = request.env['stock.quant.package'].sudo().search(
                        [('name', '=', str(packeg_name).strip())],
                        limit=1
                    )
                    if not package:
                        # Package doesn't exist
                        line_data['_package_warning'] = f"Package name '{packeg_name}' doesn't exist - order line will be created without package"
                        _logger.warning(f"Order line {idx + 1}: Package name '{packeg_name}' doesn't exist, but continuing with order line creation")
                    else:
                        line_data['_package_validated'] = True
                        _logger.info(f"Order line {idx + 1}: Package name '{packeg_name}' validated successfully")
                
                vendor_price = line_data.get('vendor_price')
                if vendor_price is not None:
                    try:
                        vendor_price_float = float(vendor_price)
                        if vendor_price_float < 0:
                            raise ValueError('vendor_price must be >= 0')
                        line_data['_vendor_price'] = vendor_price_float
                    except (TypeError, ValueError):
                        line_errors.append("vendor_price must be a non-negative number")
                
                if line_errors:
                    errors.append(f"Order line {idx + 1}: {', '.join(line_errors)}")
                    _logger.warning(f"Order line {idx + 1} validation failed: {', '.join(line_errors)}")
                else:
                    validated_lines.append((idx, line_data))
                    _logger.info(f"Order line {idx + 1} validated successfully")
            
            _logger.info(f"Validation complete: {len(validated_lines)} line(s) validated, {len(errors)} error(s)")
            
            if not validated_lines and not errors:
                _logger.warning("No order lines were validated and no errors were reported - this is unexpected")
            
            # Create order lines for validated entries
            created_lines = []
            
            if not validated_lines:
                _logger.warning(f"No order lines to create - all {len(order_data['order_line'])} line(s) failed validation")
            else:
                _logger.info(f"Creating {len(validated_lines)} order line(s)")
            for idx, line_data in validated_lines:
                try:
                    product_id = line_data.get('_product_id')
                    # Re-validate product right before creating the line to ensure it still exists
                    Product = request.env['product.product'].sudo()
                    product = Product.with_context(active_test=False).search([('id', '=', product_id)], limit=1)
                    if not product:
                        errors.append(f"Order line {idx + 1}: Product ID {product_id} no longer exists (may have been deleted)")
                        _logger.error(f"Product {product_id} not found when creating order line {idx + 1}")
                        continue
                    
                    packeg_name = line_data.get('packeg_name') or line_data.get('package_name')
                    package_warning = line_data.get('_package_warning')
                    
                    # If package validation failed
                    if package_warning:
                        errors.append(f"Order line {idx + 1}: {package_warning}")
                    
                    line_vals = {
                        'order_id': purchase_order.id,
                        'product_id': product_id,  # Use product_id directly
                        'product_qty': line_data['product_qty'],
                    }
                    

                    if '_vendor_price' in line_data:
                        line_vals['price_unit'] = line_data['_vendor_price']
                    if 'date_planned' in line_data:
                        line_vals['date_planned'] = line_data['date_planned']
                    
                    # Add package_name only if it was validated successfully
                    if packeg_name and line_data.get('_package_validated'):
                        line_vals['package_name'] = str(packeg_name).strip()
                        _logger.info(f"Adding validated package '{packeg_name}' to order line {idx + 1}")
                    elif packeg_name and not line_data.get('_package_validated'):
                        _logger.warning(f"Skipping invalid package '{packeg_name}' for order line {idx + 1}")
                    
                    _logger.info(f"Creating order line {idx + 1} with vals: {line_vals}")
                    
                    # Create order line
                    order_line = PurchaseOrderLine.create(line_vals)
                    created_lines.append(idx + 1)
                    _logger.info(f"Successfully created order line ID {order_line.id} for product {product_id} (line {idx + 1})")
                    
                    # Verify the line was created and linked to the order
                    if order_line.order_id.id != purchase_order.id:
                        _logger.error(f"Order line {order_line.id} was created but not linked to purchase order {purchase_order.id}")
                    else:
                        _logger.info(f"Order line {order_line.id} successfully linked to purchase order {purchase_order.id}")
                except Exception as line_error:
                    error_msg = str(line_error)
                    errors.append(f"Order line {idx + 1}: Failed to create - {error_msg}")
                    _logger.error(f"Failed to create order line {idx + 1} for product {product_id}: {error_msg}", exc_info=True)
            
            # Get updated order lines count
            purchase_order.invalidate_recordset(['order_line'])
            order_lines_count = len(purchase_order.order_line)
            _logger.info(f"Purchase order {purchase_order.id} now has {order_lines_count} order line(s)")
            
            # Log all order line IDs for debugging
            if order_lines_count > 0:
                line_ids = purchase_order.order_line.mapped('id')
                product_ids = purchase_order.order_line.mapped('product_id.id')
                _logger.info(f"Order lines IDs: {line_ids}, Product IDs: {product_ids}")
            else:
                _logger.warning(f"Purchase order {purchase_order.id} has NO order lines after creation!")
            
            # return errors along with the order ID
            if errors:
                result = {
                    "purchase_order_id": purchase_order.id,
                    "name": purchase_order.name,
                    "state": purchase_order.state,
                    "order_lines_count": order_lines_count,
                    "created_lines": created_lines,
                    "errors": errors,
                    "warning": "Purchase order created but some order lines failed"
                }
            else:
                result = {
                    "purchase_order_id": purchase_order.id,
                    "name": purchase_order.name,
                    "state": purchase_order.state,
                    "order_lines_count": order_lines_count,
                    "created_lines": created_lines
                }
            
            # If there was a sync error, include it in the response
            if sync_error:
                result["warning"] = f"Order created successfully but VMS sync failed: {sync_error}"
                _logger.warning(f"Purchase order {purchase_order.id} created but VMS sync had issues")
            
            return request.make_response(
                json.dumps(result),
                headers=[('Content-Type', 'application/json')]
            )
        except UserError as e:
            error_message = str(e)
            # extract order ID from error message
            order_id = None
            if 'Order ID:' in error_message:
                try:
                    order_id = int(error_message.split('Order ID:')[1].strip())
                except:
                    pass
            

            if order_id:
                _logger.warning(f"Purchase order {order_id} created but VMS sync failed: {error_message}")
                result = {
                    "purchase_order_id": order_id,
                    "warning": f"Order created but VMS sync failed: {error_message}"
                }
                return request.make_response(
                    json.dumps(result),
                    headers=[('Content-Type', 'application/json')],
                    status=207  # partial success
                )
            else:
                # No order ID found
                _logger.error("Error creating purchase order: %s", error_message)
                return request.make_response(
                    json.dumps({"error": error_message}),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )
        except Exception as e:
            _logger.error("Error creating purchase order: %s", str(e))
            return request.make_response(
                json.dumps({"error": str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500
            )

    @http.route('/mataa_api/stock/packages', type='http', auth='public', methods=['GET'], csrf=False)
    def get_stock_packages(self, **kwargs):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param(
            'mataa_order_management.api_key'
        )

        if not api_key or api_key != expected_api_key:
            return request.make_response(
                json.dumps({"error": "Invalid or missing API key"}),
                headers=[('Content-Type', 'application/json')],
                status=401
            )

        try:

            try:
                page = int(kwargs.get('page', 1))
                limit = int(kwargs.get('limit', 10))
            except ValueError:
                page = 1
                limit = 10

            search_query = kwargs.get('search', '').strip()

            offset = (page - 1) * limit

            domain = []
            if search_query:
                domain.append(('name', 'ilike', search_query))

            package_model = request.env['stock.quant.package'].sudo()

            total_count = package_model.search_count(domain)

            packages = package_model.search(
                domain,
                limit=limit,
                offset=offset,
                order='name'
            )

            result = []
            for pkg in packages:
                result.append({
                    "id": pkg.id,
                    "name": pkg.name,
                    "location": pkg.location_id.display_name if pkg.location_id else "No Location",
                    "location_id": pkg.location_id.id if pkg.location_id else None
                })

            response_data = {
                "total_records": total_count,
                "total_pages": (total_count + limit - 1) // limit if limit > 0 else 1,
                "current_page": page,
                "limit": limit,
                "count": len(result),
                "packages": result
            }

            return request.make_response(
                json.dumps(response_data),
                headers=[('Content-Type', 'application/json')],
                status=200
            )

        except Exception as e:
            _logger.exception("Failed to fetch stock packages")
            return request.make_response(
                json.dumps({"error": str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500
            )
