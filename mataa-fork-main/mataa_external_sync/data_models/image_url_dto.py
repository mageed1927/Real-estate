from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ImageUrlDTO:
    src: str
    name: str

    @staticmethod
    def from_odoo(image):
        return asdict(ImageUrlDTO(
            src=image.url,
            name=image.serialized_name,
        ))
