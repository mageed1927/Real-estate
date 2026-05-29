from odoo import models

class GeneralLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _custom_line_postprocessor(self, report, options, lines, **kwargs):
        lines = super()._custom_line_postprocessor(report, options, lines, **kwargs)

        so_col_idx = None
        for i, column in enumerate(options.get('columns', [])):
            if column.get('expression_label') == 'sale_order_col':
                so_col_idx = i
                break

        if so_col_idx is None:
            return lines

        aml_ids = []
        for line in lines:
            model, res_id = report._get_model_info_from_id(line['id'])
            if model == 'account.move.line' and res_id:
                aml_ids.append(res_id)

        if aml_ids:
            amls = self.env['account.move.line'].browse(aml_ids)
            aml_to_so_name = {aml.id: aml.sale_order_id.name for aml in amls if aml.sale_order_id}

            for line in lines:
                model, res_id = report._get_model_info_from_id(line['id'])
                if model == 'account.move.line' and res_id:
                    so_name = aml_to_so_name.get(res_id, '')

                    if 'columns' in line and so_col_idx < len(line['columns']):
                        line['columns'][so_col_idx] = {
                            'name': so_name,
                            'no_format': so_name
                        }

        return lines