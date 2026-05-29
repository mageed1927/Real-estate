from dataclasses import dataclass, asdict


@dataclass
class ItemDTO:
    description: str
    sku: str
    quantity: int
    comments: str
    purchase_order_number: str
    barcode: str

    @staticmethod
    def from_odoo(line):
        return asdict(ItemDTO(
            description=line.product_id.name,
            sku=line.product_id.default_code,
            quantity=int(line.product_qty),
            comments=line.product_id.mataa_id or None,
            purchase_order_number=line.product_description_variants,
            barcode=line.product_id.barcode or ""
        ))