from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class ProductDTO:
    id: Optional[str]
    odooId: int
    title: str
    brandName: str
    salesPrice: float
    regularPrice: float
    mainImage: str
    state: int
    BrandOdooId: Optional[int] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    tags: List[int] = field(default_factory=list)
    attributes: List[int] = field(default_factory=list)
    categories: List[int] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    Keywords: List[str] = field(default_factory=list)

    @staticmethod
    def from_odoo(product):
        sorted_images = sorted(product.image_url_ids, key=lambda img: img.sequence)
        gallery_images = [image.url for image in sorted_images] if sorted_images else []
        main_image = gallery_images[0] if gallery_images else None

        gallery_images = gallery_images[1:] if main_image else []

        # TODO: check this code , and move it to variant images when developing the feature
        variant_images = []
        for variant in product.product_variant_ids:
            sorted_variant_images = sorted(variant.variant_image_url_ids, key=lambda img: img.sequence)
            variant_images.extend([str(variant.id) + '__' + str(image.url) for image in sorted_variant_images]
                                  if sorted_variant_images else [])

        product_regular_price = product.regular_price if product.regular_price else product.list_price
        product_sale_price = product.list_price \
            if (product.list_price and product_regular_price and product.list_price <= float(product_regular_price)) \
            else 0

        brand = getattr(product, 'product_brand_id', None) or getattr(product, 'brand_id', None)

        product_kw = {kw.name for kw in getattr(product, 'product_seo_keywords', [])} if getattr(product, 'product_seo_keywords', False) else set()
        brand_kw = {kw.name for kw in getattr(brand, 'seo_keyword_ids', [])} if brand and hasattr(brand, 'seo_keyword_ids') else set()
        keywords_union = sorted(product_kw | brand_kw)

        return asdict(ProductDTO(
            id=product.id,
            odooId=product.id,
            title=product.name,
            BrandOdooId=product.product_brand_id.id if product.product_brand_id else None,
            brandName=product.product_brand_id.name if product.product_brand_id else "Unknown",
            salesPrice=product_sale_price,
            regularPrice=product_regular_price,
            description=product.description_sale if product.description_sale else None,
            sku=product.default_code if product.default_code else None,
            tags=[tag.id for tag in product.product_tag_ids] if product.product_tag_ids else [],
            attributes=[attr_line.attribute_id.id for attr_line in product.attribute_line_ids] if product.attribute_line_ids else [],
            categories=[public_categ_id.id for public_categ_id in product.public_categ_ids] if product.public_categ_ids else [],
            mainImage=main_image,
            images=gallery_images,
            Keywords=keywords_union,
            state=ProductDTO._map_mataa_status_to_product_state(product.mataa_status),
        ))

    @staticmethod
    def _map_mataa_status_to_product_state(mataa_status):

        status_mapping = {
            'unspecified': 0,  # undefined
            'publish': 1,      # Published
            'draft': 2,        # UnPublished
        }
        return status_mapping.get(mataa_status, 0)