

from odoo import models, fields, api
from odoo.exceptions import UserError

from ..services.package_service import PackageService
# from ..services.purchase_order_service import PurchaseOrderService
from ..utilities.import_packages_file_parser import ImportPackagesFileParser
# from ..utility.import_variants_error_file_generator import ImportVariantsErrorFileGenerator
# from ..services.attribute_service import AttributeService
# from ..services.category_service import CategoryService
# from ..services.product_service import ProductService
# from ..services.tag_service import TagService
# from ..services.variant_service import VariantService
# from ..services.vendor_service import VendorService
# from ..services.brand_service import BrandService


class ImportPackagesWizard(models.TransientModel):
    _name = 'import.packages.wizard'
    _description = 'Import products packaging'

    import_file = fields.Binary(string="Upload File", required=True)
    file_name = fields.Char(string="File Name")
    picking_id = fields.Many2one('stock.picking', default=lambda self: self.env.context.get('active_id'))

    @api.model
    def default_get(self, fields):
        res = super(ImportPackagesWizard, self).default_get(fields)
        pickind_ids = self.env.context.get('active_ids', [])
        if len(pickind_ids) != 1:
            raise UserError('You should select only 1 receipt!')
        picking = self.env['stock.picking'].browse(pickind_ids)
        if picking.picking_type_code != 'incoming':
            raise UserError('You should select a receipt!')
        if picking.state != 'assigned':
            raise UserError('Import packages should be only for "Ready" receipt!')
        return res

    def import_packages(self):
        """Main method for importing and processing po"""
        if not self.import_file:
            raise UserError("No file uploaded.")

        # Parse the uploaded file
        data = ImportPackagesFileParser.parse_file(self.file_name, self.import_file)
        failed_rows = []
        for idx, row in data.iterrows():
            try:
                self.process_row(row)
            except Exception as e:
                row_dict = row.fillna('').to_dict()
                row_dict['Index'] = idx + 1
                product_variant_barcode = row.get('product-variant-barcode')
                package_name = row.get('package-name')
                row_dict['Error Message'] = str(e)
                raise UserError(f"failed to import data line {idx + 1}  :\n"
                                f"Variant barcode: {product_variant_barcode}\n"
                                f"Package name: {package_name}\n"
                                f"{e}")
                # failed_rows.append(row_dict)
        # if failed_rows:
        #     return ImportVariantsErrorFileGenerator.generate_error_file(self, data, failed_rows)
        return None

    def process_row(self, row):
        # Template details
        product_variant_barcode = row.get('product-variant-barcode')
        package_name = row.get('package-name')
        quantity = row.get('quantity')

        variant = PackageService.check_existing_product(self.env, product_variant_barcode)
        if not variant:
            raise UserError("Variant wasn't found, please check your file!")

        package = PackageService.check_existing_package(self.env, package_name)
        if not package:
            raise UserError("Package wasn't found, please check your file!")

        move = PackageService.find_move(self.env, variant, self.picking_id.move_ids_without_package)
        if not move:
            raise UserError("Product doesn't exist in this receipt, please check your file!")
        # Start of the import process
        PackageService.product_assign_with_package(self.env, move, variant, package, quantity)
