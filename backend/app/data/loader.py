"""Loads the hackathon CSVs once and exposes typed lookups.

Column names follow data/README.md. If a future data drop renames columns,
adjust COLUMN_ALIASES only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import pandas as pd

from app.config import get_settings

COLUMN_ALIASES: dict[str, dict[str, str]] = {
    "product_catalogue": {},
    "smb_leads": {},
    "mock_gstin_registry": {},
    "mock_udyam_registry": {},
}

SEGMENT_CODES = {
    "Micro retail & services": "micro",
    "Professional offices": "prof",
    "Small multi-site businesses": "multi",
    "Small manufacturers": "mfg",
}
SEGMENT_NAMES = {v: k for k, v in SEGMENT_CODES.items()}


@dataclass(frozen=True)
class Product:
    id: str
    category: str
    name: str
    description: str
    unit: str
    price_min: int
    price_max: int
    setup_fee: int
    min_contract_months: int
    city_tiers: tuple[int, ...]
    min_employees: int
    min_sites: int
    requires_gstin: bool
    requires_one_of: tuple[str, ...]
    install_days: int
    target_segments: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "unit": self.unit,
            "price_min": self.price_min,
            "price_max": self.price_max,
            "setup_fee": self.setup_fee,
            "min_contract_months": self.min_contract_months,
            "city_tiers": list(self.city_tiers),
            "min_employees": self.min_employees,
            "min_sites": self.min_sites,
            "requires_gstin": self.requires_gstin,
            "requires_one_of": list(self.requires_one_of),
            "install_days": self.install_days,
            "target_segments": list(self.target_segments),
        }


@dataclass
class Dataset:
    products: dict[str, Product]
    leads: pd.DataFrame
    gstin: dict[str, dict]
    udyam: dict[str, dict]
    city_tiers: dict[str, int] = field(default_factory=dict)
    city_states: dict[str, str] = field(default_factory=dict)
    # normalised enterprise name -> Udyam records, to tell if a business is Udyam-registered
    udyam_by_name: dict[str, list[dict]] = field(default_factory=dict)


def _read(name: str) -> pd.DataFrame:
    path = get_settings().data_dir / f"{name}.csv"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return df.rename(columns=COLUMN_ALIASES.get(name, {}))


def _split(value: str, sep: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split(sep) if v.strip())


def _parse_products(df: pd.DataFrame) -> dict[str, Product]:
    out = {}
    for r in df.to_dict("records"):
        out[r["product_id"]] = Product(
            id=r["product_id"],
            category=r["category"],
            name=r["product_name"],
            description=r["description"],
            unit=r["unit"],
            price_min=int(r["price_min_inr_per_month"]),
            price_max=int(r["price_max_inr_per_month"]),
            setup_fee=int(r["one_time_setup_inr"] or 0),
            min_contract_months=int(r["min_contract_months"] or 1),
            city_tiers=tuple(int(t) for t in _split(r["available_city_tiers"], ";")),
            min_employees=int(r["min_employees"] or 1),
            min_sites=int(r["min_sites"] or 1),
            requires_gstin=r["requires_gstin"].upper() == "Y",
            requires_one_of=_split(r["requires_one_of"], "|"),
            install_days=int(r["typical_install_days"] or 1),
            target_segments=_split(r["target_segments"], ";"),
        )
    return out


@lru_cache
def get_dataset() -> Dataset:
    products = _parse_products(_read("product_catalogue"))
    leads = pd.read_csv(get_settings().data_dir / "smb_leads.csv")
    gstin = {r["gstin"].upper(): r for r in _read("mock_gstin_registry").to_dict("records")}
    udyam = {r["udyam_number"].upper(): r for r in _read("mock_udyam_registry").to_dict("records")}
    cities = leads[["city", "city_tier", "state"]].drop_duplicates("city")
    by_name: dict[str, list[dict]] = {}
    for rec in udyam.values():
        by_name.setdefault(norm_name(rec["enterprise_name"]), []).append(rec)
    return Dataset(
        products=products,
        leads=leads,
        gstin=gstin,
        udyam=udyam,
        city_tiers={c.lower(): int(t) for c, t in zip(cities.city, cities.city_tier)},
        city_states={c.lower(): s for c, s in zip(cities.city, cities.state)},
        udyam_by_name=by_name,
    )


def norm_name(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())
