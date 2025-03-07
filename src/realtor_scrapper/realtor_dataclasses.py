from dataclasses import dataclass
from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class RealtorProperty:
    price: int
    address: dict[str, str]
    url: str
    baths: float = None
    beds: float = None
    lot_sqft: int = None
    sqft: int = None
    sold_date: str = None
    sold_price: int = None
    key_facts: dict[str, str] = None


dataclass_json
@dataclass
class RealtorPropertyDetailsInterior:
    features: list[str] | None = None
    heating_cooling: list[str] | None = None


@dataclass_json
@dataclass
class RealtorPropertyDetailsExterior:
    features: list[str] | None = None
    lot_features: list[str] | None = None
    pool_spa: list[str] | None = None
    garage_parking: list[str] | None = None


@dataclass_json
@dataclass
class RealtorPropertyDetailsCommunity:
    hoa: list[str] | None = None


@dataclass_json
@dataclass
class RealtorPropertyDetailsConstruction:
    stories: int | None = None
    architectural_style: list[str] | None = None


@dataclass_json
@dataclass
class RealtorPropertyDetails:
    interior: RealtorPropertyDetailsInterior
    exterior: RealtorPropertyDetailsExterior
    community: RealtorPropertyDetailsCommunity
    construction: RealtorPropertyDetailsConstruction
