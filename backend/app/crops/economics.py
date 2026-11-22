"""Irrigation economics inputs (G10): yields, prices, Ky, technology costs.

Values and their sources: economics.yaml."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, Field, model_validator

ECONOMICS_PATH = Path(__file__).with_name("economics.yaml")

TechId = Literal["reel", "pivot", "drip"]


class Range(BaseModel):
    """A low–high range; YAML writes it as [low, high]."""

    low: float = Field(ge=0)
    high: float = Field(ge=0)

    @model_validator(mode="before")
    @classmethod
    def _from_pair(cls, v: object) -> object:
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return {"low": v[0], "high": v[1]}
        return v

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.high < self.low:
            raise ValueError("range high below low")
        return self

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2


class CropEconomics(BaseModel):
    yield_t_ha: float | None = Field(None, gt=0)
    price_zl_t: Range | None = None
    ky: float | None = Field(None, gt=0, le=2)
    ky_from: str | None = None  # Ky borrowed from another crop (FAO-33 does not list this one)


class TechCosts(BaseModel):
    efficiency: float = Field(gt=0, le=1)
    capex_zl_ha: Range
    lifetime_years: int = Field(gt=0)


class WaterSource(BaseModel):
    capex_zl: Range
    lifetime_years: int = Field(gt=0)


class EconomicsCatalog(BaseModel):
    sources: dict[str, str]
    crops: dict[str, CropEconomics]
    technologies: dict[TechId, TechCosts]
    water_source: WaterSource
    operating_zl_m3: Range


@lru_cache(maxsize=1)
def load_economics() -> EconomicsCatalog:
    return EconomicsCatalog.model_validate(yaml.safe_load(ECONOMICS_PATH.read_text(encoding="utf-8")))
