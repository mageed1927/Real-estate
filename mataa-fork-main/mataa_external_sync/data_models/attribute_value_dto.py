from dataclasses import dataclass, field, asdict
from typing import List, Optional

@dataclass
class AttributeValueDTO:
    id: Optional[int]
    attributeName: str
    name: str
    odooId: int

    @staticmethod
    def from_odoo(value_id):
        return asdict(AttributeValueDTO(
            id=value_id.id,
            attributeName=value_id.attribute_id.name,
            name=value_id.name,
            odooId=value_id.id,
        ))
