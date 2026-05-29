from odoo import api, models

from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class CategoryService:

    @staticmethod
    def get_category_by_complete_path(env, complete_path):

        if not complete_path:
            return False

        category_names = [name.strip() for name in complete_path.split('/')]

        current_category = False
        parent_id = False

        for name in category_names:
            if not name:
                continue

            domain = [('name', '=', name)]
            if parent_id:
                domain.append(('parent_id', '=', parent_id))
            else:
                domain.append(('parent_id', '=', False))

            current_category = env['product.public.category'].sudo().search(domain, limit=1)
            if not current_category:
                return False

            parent_id = current_category.id

        return current_category

    @staticmethod
    def get_or_create_web_category(env, category_path):

        if not category_path:
            return False

        # First try to find existing category by traversing the path
        existing_category = CategoryService.get_category_by_complete_path(env, category_path)
        if existing_category:
            return existing_category

        # If not found, create the category hierarchy
        category_names = [name.strip() for name in category_path.split('/')]

        parent_id = False
        final_category = False

        for category_name in category_names:
            if not category_name:
                continue

            domain = [('name', '=', category_name)]
            if parent_id:
                domain.append(('parent_id', '=', parent_id))
            else:
                domain.append(('parent_id', '=', False))

            category = env['product.public.category'].search(domain, limit=1)

            if not category:
                category = env['product.public.category'].sudo().create({
                    'name': category_name,
                    'parent_id': parent_id
                })

            parent_id = category.id
            final_category = category

        return final_category

    @staticmethod
    def assign_public_categories(env, product_template, web_categories):

        Category = env['product.public.category'].sudo()
        if not web_categories:
            product_template.sudo().write({
                'public_categ_ids': [(6, 0, [])]
            })
            return

        web_cat_ids = []

        if isinstance(web_categories, list):

            # List of integers (IDs)
            if all(isinstance(x, int) for x in web_categories):
                categories = Category.browse(web_categories).exists()

                if len(categories) != len(web_categories):
                    raise UserError("One or more web category IDs do not exist")

                web_cat_ids = categories.ids

            # List of strings (names)
            elif all(isinstance(x, str) for x in web_categories):
                for name in web_categories:
                    category = Category.search([('name', '=ilike', name.strip())], limit=1)
                    if not category:
                        raise UserError(f"Web category not found: {name}")
                    web_cat_ids.append(category.id)

            else:
                raise UserError("web_categories list must contain only int IDs or string names")

        elif isinstance(web_categories, str):

            category_names = [name.strip() for name in web_categories.split(',')]

            for name in category_names:
                category = Category.search([('name', '=ilike', name)], limit=1)
                if not category:
                    raise UserError(f"Web category not found: {name}")
                web_cat_ids.append(category.id)

        else:
            raise UserError("Invalid format for web_categories")

        # Assign categories
        product_template.sudo().write({
            'public_categ_ids': [(6, 0, web_cat_ids)]
        })

    @staticmethod
    def get_or_create_category(env, category_name):

        category = env['product.category'].sudo().search([('name', '=', category_name)], limit=1)
        if not category:
            category = env['product.category'].sudo().create({'name': category_name})
        return category
    #
    # @staticmethod
    # def get_or_create_web_category(env, category_name):
    #     """Get or create a product category"""
    #     category = env['product.public.category'].search([('display_name', '=', category_name)], limit=1)
    #     if not category:
    #         category = env['product.public.category'].create({'name': category_name})
    #     return category
    #
    # @staticmethod
    # def assign_public_categories(env, product_template, web_categories):
    #     """Assign categories (both web and functional) to the product template"""
    #     if web_categories:
    #         web_cat_ids = env['product.public.category'].search([('name', 'in', web_categories.split(','))])
    #         product_template.write({'public_categ_ids': [(6, 0, web_cat_ids.ids)]})
