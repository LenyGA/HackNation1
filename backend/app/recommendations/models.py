"""Rule engine types: a Rule checks values computed for the parcel and yields a Recommendation with evidence.

Pure, no I/O. Polish texts live in `texts_pl.py`; rules only compute the values that fill them.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.analysis.assessment import Assessment, CurrentState
from app.analysis.causes import Cause, CauseId
from app.analysis.context import AnalysisInputs
from app.analysis.history import HistoryResult
from app.analysis.soil import SoilProperties
from app.analysis.terrain import TerrainResult
from app.core.models import Indicator
from app.crops.catalog import Crop
from app.sources.hydro import HydroData


class Category(StrEnum):
    RETENTION = "retention"
    AGROTECH = "agrotech"
    IRRIGATION = "irrigation"


class Horizon(StrEnum):
    """When to act: from the analysis date, or while preparing the next growing season."""

    NOW = "now"
    SEASON = "season"


# Mandatory order of actions (CLAUDE.md rule 2): retention → agrotechnics → irrigation.
CATEGORY_ORDER = [Category.RETENTION, Category.AGROTECH, Category.IRRIGATION]

LocationKind = Literal["ditch", "depression", "flow_path", "outlet", "wetland", "water_body"]
ParamValue = str | int | float


class Location(BaseModel):
    """A place on the map that a recommendation refers to (plan step M7.4)."""

    kind: LocationKind
    geometry: dict[str, Any] = Field(description="GeoJSON geometry in EPSG:4326.")


class Recommendation(BaseModel):
    number: int = Field(description="1-based position in the final, ordered list; used by map markers.")
    id: str = Field(description="Id of the rule that produced the recommendation.")
    category: Category
    priority: int
    template: str = Field(description="Key of the Polish text template.")
    title_pl: str
    text_pl: str
    params: dict[str, ParamValue] = Field(description="Computed values filled into the template.")
    evidence: list[Indicator] = Field(min_length=1, description="Numbers that triggered the rule.")
    locations: list[Location] = Field(default_factory=list)
    horizon: Horizon = Horizon.SEASON


@dataclass(frozen=True)
class RuleContext:
    """A complete assessment plus the inputs it was computed from."""

    assessment: Assessment
    inputs: AnalysisInputs

    @property
    def crop(self) -> Crop:
        return self.inputs.crop

    @property
    def current(self) -> CurrentState:
        assert self.assessment.current is not None  # guaranteed by recommend()
        return self.assessment.current

    @property
    def history(self) -> HistoryResult | None:
        return self.assessment.history

    @property
    def soil(self) -> SoilProperties | None:
        return self.assessment.soil

    @property
    def terrain(self) -> TerrainResult | None:
        return self.assessment.terrain

    @property
    def hydro(self) -> HydroData | None:
        return self.assessment.hydro

    def cause(self, cause_id: CauseId) -> Cause | None:
        return next((c for c in self.assessment.causes if c.id == cause_id), None)


def _no_params(_: RuleContext) -> dict[str, ParamValue]:
    return {}


def _no_locations(_: RuleContext) -> list[Location]:
    return []


@dataclass(frozen=True)
class Rule:
    id: str
    category: Category
    priority: int  # order within the category, lower first
    condition: Callable[[RuleContext], bool]
    evidence: Callable[[RuleContext], list[Indicator]]
    params: Callable[[RuleContext], dict[str, ParamValue]] = field(default=_no_params)
    locations: Callable[[RuleContext], list[Location]] = field(default=_no_locations)
    template: str = ""  # defaults to the rule id

    @property
    def template_key(self) -> str:
        return self.template or self.id
