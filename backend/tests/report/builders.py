"""Report scenarios built from the recommendation/analysis builders (no network)."""

from datetime import UTC, date, datetime
from typing import Any

from app.recommendations.irrigation import irrigation_advice
from app.report.builder import ParcelSource, build_report
from app.report.models import Report
from app.report.storage import new_report_id
from tests.recommendations.builders import basin, hydro, scenario

CREATED = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)


def report_for(**kw: Any) -> Report:
    a, inputs, recs = scenario(**kw)
    irr = irrigation_advice(a, inputs, today=inputs.analysis_date)
    return build_report(
        report_id=new_report_id(),
        created_at=CREATED,
        inputs=inputs,
        assessment=a,
        recommendations=recs,
        irrigation=irr,
        parcel_source=ParcelSource(fetched_at=CREATED),
    )


def rich_report() -> Report:
    """Dry summer, basin with a ditch and trees: many recommendations, map features."""
    return report_for(surface=basin, hydro_data=lambda p: hydro(p, ditch_m=200.0, trees_m=300.0))


def two_missing_report() -> Report:
    """Soil and terrain missing (plus satellite and land cover, which the builders never provide)."""
    return report_for(soil=False, dem=False)


def no_weather_report() -> Report:
    return report_for(weather=False)


def off_season_report() -> Report:
    return report_for(crop_id="winter_wheat", day=date(2024, 11, 21))


SCENARIOS = {
    "rich": rich_report,
    "two_missing": two_missing_report,
    "no_weather": no_weather_report,
    "off_season": off_season_report,
    "tilted_no_hydro": lambda: report_for(hydro_data=False),
    # Fruit crops (plan33 M6): summer, dormancy before bud break, end of season after the fruit harvest.
    "orchard_summer": lambda: report_for(
        crop_id="orchard_pome", surface=basin, hydro_data=lambda p: hydro(p, ditch_m=200.0)
    ),
    "orchard_dormant": lambda: report_for(crop_id="orchard_cherry", day=date(2024, 3, 25)),
    "berry_late": lambda: report_for(crop_id="berry_bushes", day=date(2024, 9, 20)),
    # After the vegetation period (30 Sep) but before leaf fall: crop_on_field without in_vegetation.
    "orchard_october": lambda: report_for(crop_id="orchard_pome", day=date(2024, 10, 15)),
}
