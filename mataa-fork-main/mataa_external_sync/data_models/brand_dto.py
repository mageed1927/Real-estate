from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class BrandDTO:
    id: int
    Name: str
    LogoUrl: str
    OdooId: str
    Keywords: List[str] = field(default_factory=list)

    @staticmethod
    def from_odoo(brand):
        brand_keywords = [kw.name for kw in getattr(brand, 'seo_keyword_ids', [])] if hasattr(brand, 'seo_keyword_ids') else []
        return asdict(BrandDTO(
            id=brand.id,
            Name=brand.name,
            LogoUrl=brand.logo_url or "",
            OdooId=brand.id,
            Keywords=brand_keywords,
        ))
