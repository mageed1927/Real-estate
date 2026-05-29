from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..utility.customers_file_parser import CustomersFileParser
from ..services.customer_service import CustomerService
from ..services.country_service import CountryService
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class PreSyncCustomersWizard(models.TransientModel):
    _name = 'presync.customers.wizard'
    _description = 'Initial Presync customers'

    import_file = fields.Binary(string="Upload File", required=True)
    file_name = fields.Char(string="File Name")

    def presync_customers(self):
        if not self.import_file:
            raise UserError("No file uploaded.")

        # Parse the uploaded file
        data = CustomersFileParser.parse_file(self.file_name, self.import_file)

        batch_size = 50  # Define the batch size
        customer_data_list = []
        skipped_customers = []  # Collect skipped customers

        # Process data in batches
        for start in range(0, len(data), batch_size):
            _logger.info(f"Processing Batch: {start} ~ {start + batch_size}")
            batch = data.iloc[start:start + batch_size]
            for idx, row in batch.iterrows():
                try:
                    _logger.info(f"# Processing Row {idx}")
                    is_skipped, customer_data = self.process_row(row)
                    if is_skipped:
                        skipped_customers.append(customer_data)  # Collect skipped customer information
                    elif customer_data:
                        customer_data_list.append(customer_data)  # Collect valid customer data
                except Exception as e:
                    _logger.error(f"Failed to process row {idx + 1}: {e}")
                    raise UserError(f"Error processing row {idx + 1}:\n{e}")

        # Log start of customer create process
        _logger.info("Starting customer create process for all processed rows...")

        # Update customers after all rows are processed
        for customer_data in customer_data_list:
            try:
                _logger.info(f"creating customer: {customer_data['customer_name']} (Mataa ID: {customer_data['mataa_id']})")

                existing_customer = customer_data['customer_exists']
                if not existing_customer:
                    created_customer = CustomerService.create_customer(
                        env=self.with_context(pre_sync=True).env,
                        mataa_id=customer_data['mataa_id'] if customer_data['mataa_id'] else None,
                        customer_name=customer_data['customer_name'] if customer_data['customer_name'] else None,
                        customer_email=customer_data['customer_email'] if customer_data['customer_email'] else None,
                        street=customer_data['street'] if customer_data['street'] else None,
                        street2=customer_data['street2'] if customer_data['street2'] else None,
                        country_id=customer_data['country_id'] if customer_data['country_id'] else None,
                        city=customer_data['city'] if customer_data['city'] else None,
                        birthdate_date=customer_data['birthdate_date'] if customer_data['birthdate_date'] else None,
                        gender=customer_data['gender'] if customer_data['gender'] else None,
                        phone=customer_data['phone'] if customer_data['phone'] else None,
                    )
                else:
                    updated_customer = CustomerService.update_customer(
                        env=self.with_context(pre_sync=True).env,
                        mataa_id=customer_data['mataa_id'] if customer_data['mataa_id'] else None,
                        customer_name=customer_data['customer_name'] if customer_data['customer_name'] else None,
                        customer_email=customer_data['customer_email'] if customer_data['customer_email'] else None,
                        street=customer_data['street'] if customer_data['street'] else None,
                        street2=customer_data['street2'] if customer_data['street2'] else None,
                        country_id=customer_data['country_id'] if customer_data['country_id'] else None,
                        city=customer_data['city'] if customer_data['city'] else None,
                        birthdate_date=customer_data['birthdate_date'] if customer_data['birthdate_date'] else None,
                        gender=customer_data['gender'] if customer_data['gender'] else None,
                        phone=customer_data['phone'] if customer_data['phone'] else None,
                    )

            except Exception as e:
                raise UserError(f"Error while updating : \n{customer_data}\n -{e}")

        # Display a notification with the skipped customers if any
        if skipped_customers:
            skipped_customer_names = ", ".join(skipped_customers)
            _logger.info(f"The following customers were skipped: {skipped_customer_names}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Note: Skipped Customers (Already Exists)"),
                    'message': _("The following customers were skipped: %s") % skipped_customer_names,
                    'sticky': True,
                }
            }

    def process_row(self, row):
        mataa_id = row.get('customer_id')
        address_1 = row.get('address_1')
        address_2 = row.get('address_2')
        country = row.get('country')
        city = row.get('state_name')
        user_email = row.get('user_email')
        display_name = row.get('display_name')
        date_of_birth = row.get('date_of_birth')
        first_name = row.get('first_name')
        last_name = row.get('last_name')
        gender = row.get('sex')
        phone_number = row.get('registered_phone_number')

        if not display_name:
            raise UserError(f"no display name was found for customer with id {mataa_id}")

        if not display_name:
            raise UserError(f"no mataa_id was found for customer with display_name {display_name}")

        existing_country = CountryService.get_country(env=self.env, country_name=country)
        if not existing_country:
            existing_country = CountryService.get_country(env=self.env, country_name="Libya")

        customer_exists = False
        customer = CustomerService.get_customer(env=self.env, mataa_id=mataa_id)
        if customer:
            customer_exists = True
            # raise UserError(f"customer with mataa_id {mataa_id} already exists")

        customer_data = {
            'mataa_id': mataa_id,
            'customer_name': display_name,
            'customer_email': user_email,
            'street': address_1,
            'street2': address_2,
            'country_id': existing_country.id,
            'city': city,
            'birthdate_date': self.parse_date(date_of_birth),
            'gender': gender,
            'phone': phone_number,
            'customer_exists': customer_exists
        }

        return False, customer_data

    def parse_date(self, date_string, date_format='%Y-%m-%d'):
        """
        Parses a date string to a datetime.date object if in the correct format.
        Returns None if date_string is None or an empty string.
        """
        if not date_string:
            return None
        try:
            date_obj = datetime.strptime(date_string, "%d/%m/%Y")

            formatted_date = date_obj.strftime(date_format)
            return formatted_date
        except ValueError as e:
            raise ValueError(f"Invalid date format for '{date_string}'. Expected format: {date_format}.")