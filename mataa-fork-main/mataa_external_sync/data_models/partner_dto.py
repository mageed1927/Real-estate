# -*- coding: utf-8 -*-

from dataclasses import dataclass, asdict
from datetime import datetime
import re


@dataclass
class PartnerDTO:
    odooId: int
    FirstName: str
    LastName: str
    Email: str
    Phone: str
    City: str
    Street1: str
    Street2: str
    birthdate: str
    gender: int
    suspended: bool
    @staticmethod
    def _map_gender(gender_str: str) -> int:
        gender_map = {
            "female": 1,
            "male": 2,
        }
        return gender_map.get(gender_str, 0)  # Default to Undefined (0)

    @staticmethod
    def _format_ly_mobile_phone(phone_number: str | None) -> str:
        if not phone_number:
            return ""  # Return empty if input is None or empty

        # 1. Basic cleaning: remove spaces, dashes, parentheses
        cleaned_number = re.sub(r"[\s\-()]", "", phone_number)

        # 2. Handle potential international prefixes and standardize
        if cleaned_number.startswith("+218"):
            number_part = cleaned_number[1:]  # Keep 218...
        elif cleaned_number.startswith("00218"):
            number_part = cleaned_number[2:]  # Keep 218...
        elif cleaned_number.startswith("091") and len(cleaned_number) == 10:
            number_part = "218" + cleaned_number[1:]  # Convert 091.. to 21891..
        elif cleaned_number.startswith("092") and len(cleaned_number) == 10:
            number_part = "218" + cleaned_number[1:]  # Convert 092.. to 21892..
        elif cleaned_number.startswith("094") and len(cleaned_number) == 10:
            number_part = "218" + cleaned_number[1:]  # Convert 094.. to 21894..
        else:
            number_part = cleaned_number  # Use as is for further validation

        if re.fullmatch(r"^218(91|92|94)\d{7}$", number_part):
            return number_part  # Valid format, return it
        else:
            return ""

    @staticmethod
    def from_odoo(partner):
        # todo: check customer FirstName & LastName
        name_parts = (partner.name or "").strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        formatted_phone = PartnerDTO._format_ly_mobile_phone(partner.phone)
        return asdict(PartnerDTO(
            odooId=partner.id,
            FirstName=first_name,
            LastName=last_name,
            Email=partner.email or "",
            Phone=formatted_phone or "",
            City=partner.city or "",
            Street1=partner.street or "",
            Street2=partner.street2 or "",
            birthdate=partner.birthdate_date.strftime("%Y-%m-%dT%H:%M:%SZ") if partner.birthdate_date else "1970-01-01T00:00:00Z",
            gender=PartnerDTO._map_gender(partner.gender),
            suspended=partner.is_suspended
        ))
