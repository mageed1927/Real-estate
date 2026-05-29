from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class VariantDTO:
    id: Optional[int]
    odooId: int
    productOdooId: int
    title: str
    price: float
    isOnStock: bool
    discountPrice: float
    isActive: bool
    isOnDiscount: bool
    isPrimary: bool
    was_in_house: bool
    description: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    AttributeOdooId: List[int] = field(default_factory=list)

    @staticmethod
    def from_odoo(variant):
        variant_regular_price = variant.regular_price if variant.regular_price and variant.regular_price > 0 else variant.lst_price
        variant_sale_price = variant.lst_price if variant.lst_price else None

        is_on_discount = variant_regular_price != variant_sale_price

        product_quantity = variant.get_mataa_quantity()
        tmpl = (variant.product_tmpl_id._origin or variant.product_tmpl_id)

        return asdict(VariantDTO(
            id=int(variant._origin) or variant.id,
            odooId=int(variant._origin) or variant.id,
            productOdooId = tmpl.id if isinstance(tmpl.id, int) else None,
            title=variant.name,
            price=variant_regular_price if is_on_discount else (variant_sale_price or variant_regular_price),
            isOnStock=product_quantity > 0,
            discountPrice=variant_sale_price if variant_sale_price else (variant_sale_price or variant_regular_price),
            isActive=True,
            isOnDiscount=is_on_discount,
            isPrimary=True,
            was_in_house=variant.was_in_house,
            description=variant.description_sale if variant.description_sale else None,
            sku=variant.default_code if variant.default_code else None,
            barcode=variant.barcode if variant.barcode else None,
            AttributeOdooId=[attribute_value.product_attribute_value_id.id for attribute_value in variant.product_template_attribute_value_ids],
        ))
