from odoo import models, fields, api
from odoo.exceptions import UserError
from ..utility.vendors_file_parser import VendorsFileParser
from ..services.vendor_service import VendorService


class PreSyncVendorsWizard(models.TransientModel):
    _name = 'presync.vendors.wizard'
    _description = 'Initial Presync vendors'

    import_file = fields.Binary(string="Upload File", required=True)
    file_name = fields.Char(string="File Name")

    def presync_vendors(self):
        if not self.import_file:
            raise UserError("No file uploaded.")

        # Parse the uploaded file
        data = VendorsFileParser.parse_file(self.file_name, self.import_file)

        # Iterate through rows in the DataFrame
        for idx, row in data.iterrows():
            try:
                self.process_row(row)
            except Exception as e:
                raise UserError(f"failed to import data line {idx + 1}  :\n"
                                f"{e}")

    def process_row(self, row):
        mataa_id = row.get('ID')
        name = row.get('name')
        email = row.get('email')
        shipping_address_1 = row.get('shipping_address_1')

        if not name:
            return

        vendor = VendorService.get_vendor(env=self.env, vendor_name=name)
        if vendor:
            raise UserError(f"vendor with name {name} already exists")

        vendor = VendorService.create_vendor(
            env=self.with_context(pre_sync=True).env,
            mataa_id=mataa_id,
            vendor_name=name,
            vendor_email=email,
            vendor_address=shipping_address_1)
