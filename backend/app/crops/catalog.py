from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

CATALOG_PATH = Path(__file__).with_name("catalog.yaml")


class Crop(BaseModel):
    id: str
    name_pl: str


@lru_cache
def load_crops() -> dict[str, Crop]:
    raw = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
    return {c["id"]: Crop.model_validate(c) for c in raw["crops"]}


def get_crop(crop_id: str) -> Crop | None:
    return load_crops().get(crop_id)
