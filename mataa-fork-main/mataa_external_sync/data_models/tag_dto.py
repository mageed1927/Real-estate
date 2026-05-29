from dataclasses import dataclass, field, asdict


@dataclass
class TagDTO:
    id: int
    name: str
    color: str

    @staticmethod
    def from_odoo(tag):
        return asdict(TagDTO(
            id=tag.id,
            name=tag.name,
            color=tag.color
        ))
