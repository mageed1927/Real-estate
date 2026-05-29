from odoo import models, fields, api
from odoo.exceptions import UserError
from ..utility.categories_file_parser import CategoriesFileParser
from ..services.category_service import CategoryService
from odoo.addons.mataa_external_sync.services.category_sync_service import CategorySyncService
from concurrent.futures import ThreadPoolExecutor, as_completed

class PreSyncCategoriesWizard(models.TransientModel):
    _name = 'presync.categories.wizard'
    _description = 'Initial Presync categories'

    import_file = fields.Binary(string="Upload File", required=True)
    file_name = fields.Char(string="File Name")

    def presync_categories(self):
        if not self.import_file:
            raise UserError("No file uploaded.")

        # Parse the uploaded file
        data = CategoriesFileParser.parse_file(self.file_name, self.import_file)

        # Topologically sort categories
        sorted_categories = CategoriesFileParser.topological_sort(data)

        # problems = self._validate_wc(sorted_categories)
        # if problems and len(problems) > 0:
        #     raise UserError(f"the following categories doesn't exist on wooCommerce :\n"
        #                     f"{', '.join(map(str, problems))}")

        # Iterate through rows in the DataFrame
        for idx, row in enumerate(sorted_categories):
            try:
                self.process_row(row)
            except Exception as e:
                raise UserError(f"failed to import data line {idx+1}  :\n"
                                f"{e}")

    def process_row(self, row):
        mataa_id = row.get('mataa_id')
        mataa_parent_id = row.get('mataa_parent_id')
        name = row.get('name')

        if not mataa_id:
            return

        if not name:
            return

        created = CategoryService.create_web_category(
            env=self.with_context(pre_sync=True).env,
            name=name,
            mataa_id=mataa_id,
            mataa_parent_id=mataa_parent_id
        )

    def _validate_wc(self, data):
        problems = []

        def validate_category(row):
            mataa_id = row.get('mataa_id')
            try:
                wc_category = CategorySyncService.get_by_id(target_id=mataa_id)
                if not wc_category.get('id'):
                    raise ValueError(f"Category {mataa_id} Doesn't exist on WooCommerce")
                return None  # No problem
            except Exception as e:
                return mataa_id  # Problematic ID

        for row in data:
            result = validate_category(row)
            if result is not None:  # If there's an error, it returns the problematic mataa_id
                problems.append(result)

        return problems






