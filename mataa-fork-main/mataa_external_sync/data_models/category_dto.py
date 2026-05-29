from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class CategoryDTO:
    id: Optional[int]
    OdooId: Optional[int]
    name: str
    parentCategoryOdooId: int
    imageUrl: str
    entityState: int

    @staticmethod
    def from_odoo(category):

        return asdict(CategoryDTO(
            id=category.id if category.id else None,
            OdooId=category.id if category.id else None,
            name=category.name,
            imageUrl=category.image_url or "",
            parentCategoryOdooId=category.parent_id.id if category.parent_id.id else None,
            entityState=1 if category.active else 0
        ))
