from dataclasses import dataclass, asdict, field
from typing import List

from odoo.http import request
from .item_dto import ItemDTO
from datetime import date


@dataclass
class JobDTO:
    name: str
    date: str
    type: str
    service_type: str
    job_type: str
    deliver_to_collect_from: str
    do_number: str
    address: str
    webhook_url: str
    items: List[ItemDTO] = field(default_factory=list)

    @staticmethod
    def from_odoo(blanket_order):
        odoo_hosting_base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return asdict(JobDTO(
            name=blanket_order.name,
            date=str(date.today()),
            type="Collection",
            service_type="Collection",
            job_type="Collection",
            deliver_to_collect_from=blanket_order.vendor_id.name,
            do_number=blanket_order.name,
            address=blanket_order.vendor_id.contact_address_complete,
            webhook_url=f"{odoo_hosting_base_url}/api/blanket-order/{blanket_order.id}/close",
            items=[ItemDTO.from_odoo(line) for line in blanket_order.line_ids] if blanket_order.line_ids else [],
        ))