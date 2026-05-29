from odoo import models, fields, api
from odoo.exceptions import UserError
from ..utility.brands_file_parser import BrandsFileParser
from ..services.brand_service import BrandService


class PreSyncBrandsWizard(models.TransientModel):
    _name = 'presync.brands.wizard'
    _description = 'Initial Presync brands'

    import_file = fields.Binary(string="Upload File", required=True)
    file_name = fields.Char(string="File Name")

    def presync_brands(self):
        if not self.import_file:
            raise UserError("No file uploaded.")

        # Parse the uploaded file
        data = BrandsFileParser.parse_file(self.file_name, self.import_file)

        # Iterate through rows in the DataFrame
        for idx, row in data.iterrows():
            try:
                self.process_row(row)
            except Exception as e:
                raise UserError(f"failed to import data line {idx + 1}  :\n"
                                f"{e}")

    def process_row(self, row):
        brand_mataa_id = row.get('mataa_id')
        brand_id = row.get('id')
        brand_name = row.get('name')

        if not brand_mataa_id:
            return

        if not brand_id:
            return

        if not brand_name:
            return

        brand = BrandService.get_brand(env=self.env, brand_id=brand_id)
        if not brand:
            raise UserError(f"brand \n id:{brand_id} \n name:{brand_name} \n mataa_id: {brand_mataa_id} \n wasn't found")

        BrandService.update_brand(
            env=self.with_context(pre_sync=True).env,
            brand_id=brand_id,
            name=brand_name,
            mataa_id=brand_mataa_id
        )