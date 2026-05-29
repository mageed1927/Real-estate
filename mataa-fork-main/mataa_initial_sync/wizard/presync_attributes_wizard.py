from odoo import models, fields, api
from odoo.exceptions import UserError
from ..utility.attributes_file_parser import AttributesFileParser
from ..services.attribute_service import AttributeService
# from odoo.addons.mataa_external_sync.services.attribute_sync_service import AttributeSyncService
# from odoo.addons.mataa_external_sync.services.attribute_value_sync_service import AttributeValueSyncService

class PreSyncAttributesWizard(models.TransientModel):
    _name = 'presync.attributes.wizard'
    _description = 'Initial Presync attributes'

    import_file = fields.Binary(string="Upload File", required=True)
    file_name = fields.Char(string="File Name")

    def presync_attributes(self):
        if not self.import_file:
            raise UserError("No file uploaded.")

        # Parse the uploaded file
        data = AttributesFileParser.parse_file(self.file_name, self.import_file)

        # Iterate through rows in the DataFrame
        for idx, row in data.iterrows():
            try:
                self.process_row(row)
            except Exception as e:
                raise UserError(f"failed to import data line {idx + 1}  :\n"
                                f"{e}")

    def process_row(self, row):
        attribute_mataa_id = row.get('attribute_mataa_id')
        attribute_name = row.get('attribute_name')
        value_mataa_id = row.get('value_mataa_id')
        value_name = row.get('value_name')

        if not attribute_mataa_id:
            return

        if not attribute_name:
            return

        if not value_mataa_id:
            return

        if not value_name:
            return

        # # checking the attribute
        # try:
        #     wc_attribute = AttributeSyncService.get_by_id(target_id=attribute_mataa_id)
        #
        #     if not wc_attribute.get('id'):
        #         raise UserError(f"Attribute {attribute_mataa_id} Doesn't exists on WooCommerce")
        # except Exception as e:
        #     raise UserError(f"Error Fetching Attribute From WooCommerce \n {e}")
        #
        # # checking the attribute value
        # try:
        #     wc_attribute_value = AttributeValueSyncService.get_by_id(target_id=value_mataa_id, parent_id=attribute_mataa_id)
        #
        #     if not wc_attribute_value.get('id'):
        #         raise UserError(f"Attribute-Value {value_mataa_id} Doesn't exists on WooCommerce")
        # except Exception as e:
        #     raise UserError(f"Error Fetching Attribute-Value From WooCommerce \n {e}")

        attribute = AttributeService.get_attribute(env=self.env, mataa_id=attribute_mataa_id)
        if not attribute:
            attribute = AttributeService.create_attribute(
                env=self.with_context(pre_sync=True).env,
                name=attribute_name,
                mataa_id=attribute_mataa_id)

        attribute_value = AttributeService.create_attribute_value(
            env=self.with_context(pre_sync=True).env,
            attribute_mataa_id=attribute_mataa_id,
            mataa_id=value_mataa_id,
            name=value_name
        )