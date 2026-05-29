from odoo import models, api


class AdditionalBarcode(models.Model):
    _inherit = 'product.product'

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, count=False):
        """
        Extend product search so that searching on 'barcode'
        also checks additional barcodes in barcode_ids.name.
        This affects any search done with [('barcode', ...)] in the domain.
        """
        domain = domain or []
        new_domain = []

        for arg in domain:
            if (
                isinstance(arg, (list, tuple))
                and len(arg) == 3
                and arg[0] == 'barcode'
                and arg[1] in ('=', 'ilike', '=ilike')
            ):
                # Search on main barcode OR additional barcodes
                new_domain.extend([
                    '|',
                    ('barcode', arg[1], arg[2]),
                    ('barcode_ids.name', arg[1], arg[2]),
                ])
            else:
                new_domain.append(arg)

        # Call original _search with the modified domain
        ids = super()._search(
            new_domain,
            offset=offset,
            limit=limit,
            order=order,
        )

        if count:
            return len(ids)
        return ids

    @api.model
    def mataa_translate_barcode(self, barcode):
        """
        RPC called from JS:
        if 'barcode' matches an additional barcode, return the main barcode.
        If nothing matches, return the original scanned value.
        """
        if not barcode:
            return barcode

        # Optional but cleaner: enforce ACLs
        self.check_access_rights('read')
        self.check_access_rule('read')

        product = self.search([
            '|',
            ('barcode', '=', barcode),
            ('barcode_ids.name', '=', barcode),
        ], limit=1)

        # If product has a main barcode, use it; otherwise keep the original.
        return product.barcode or barcode
