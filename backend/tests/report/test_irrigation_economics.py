"""G10 / M5.4: technology and economics block in the report JSON, the full and the basic PDF."""

from app.report.pdf import render_html
from app.report.texts import num
from tests.report.builders import no_weather_report, report_for


def test_block_present_with_sentences() -> None:
    for crop in ("rye", "potato", "sugar_beet", "winter_rapeseed", "field_vegetables"):
        r = report_for(crop_id=crop)
        ie = r.irrigation_economics
        assert ie is not None, crop
        assert ie.technology_text_pl and ie.text_pl, crop
        for line in ie.technology_text_pl + ie.text_pl:
            assert "{{" not in line and "None" not in line and "brak danych" not in line, (crop, line)


def test_rye_and_potato_get_different_verdicts() -> None:
    rye = report_for(crop_id="rye").irrigation_economics
    potato = report_for(crop_id="potato").irrigation_economics
    assert rye is not None and potato is not None
    assert rye.verdict == "unprofitable" and potato.verdict == "profitable"
    assert rye.benefit_zl_ha_low is not None
    # The sentence states the same rounded number as the JSON field.
    assert num(rye.benefit_zl_ha_low, 50).replace("\xa0", " ") in rye.text_pl[0].replace("\xa0", " ")


def test_vegetables_use_drip_efficiency_in_the_water_plan() -> None:
    r = report_for(crop_id="field_vegetables")
    assert r.irrigation_economics is not None and r.irrigation_economics.technology == "drip"
    assert r.water_plan is not None and r.water_plan.efficiency_pct == 90
    assert any("kroplowa" in p for p in r.water_plan.text_pl)


def test_sprinkler_crops_keep_75_percent() -> None:
    r = report_for(crop_id="potato")
    assert r.water_plan is not None and r.water_plan.efficiency_pct == 75


def test_no_block_without_complete_assessment() -> None:
    assert no_weather_report().irrigation_economics is None


def test_no_soil_says_so() -> None:
    ie = report_for(crop_id="potato", soil=False).irrigation_economics
    assert ie is not None and ie.status == "no_balance" and ie.verdict == "unknown"
    assert "Bez danych o glebie" in ie.text_pl[0]


def test_assumptions_are_editable_defaults_with_sources() -> None:
    ie = report_for(crop_id="potato").irrigation_economics
    assert ie is not None
    a = ie.assumptions
    assert a.yield_t_ha == 30.2 and a.ky == 1.1 and a.price_zl_t_low is not None
    assert "GUS" in ie.source and "FAO" in ie.source and "założenia" in ie.source


def test_borrowed_ky_is_stated() -> None:
    ie = report_for(crop_id="rye").irrigation_economics
    assert ie is not None and any("pszenicy ozimej" in a for a in ie.assumptions_pl)


def test_full_and_basic_pdf_show_the_verdict() -> None:
    r = report_for(crop_id="potato")
    ie = r.irrigation_economics
    assert ie is not None
    full = render_html(r, variant="full")
    assert "Jaka instalacja i czy nawadnianie się opłaca" in full and ie.verdict_pl in full
    assert "Założenia" in full
    basic = render_html(r, variant="basic")
    assert "Nawadnianie: jaka instalacja i czy się opłaca" in basic and ie.technology_pl in basic


def test_rapeseed_names_only_the_missing_ky() -> None:
    ie = report_for(crop_id="winter_rapeseed").irrigation_economics
    assert ie is not None and ie.status == "no_crop_data"
    assert "FAO-33" in ie.text_pl[0] and "plonu odniesienia" not in ie.text_pl[0]


def test_tech_sentence_with_zero_need_and_one_width() -> None:
    from app.analysis.parcel_shape import ParcelShape
    from app.crops.catalog import load_crops
    from app.recommendations.irrigation_tech import choose_technology
    from app.report.irrigation_economics import _Rounded
    from app.report.texts import render_text

    def rounded(width: float) -> _Rounded:
        return _Rounded(
            75, 950.0, width, "Deszczownia szpulowa", None, None, None, None, None, None, None, 0.5
        )

    crops = load_crops()
    none = choose_technology(crops["potato"], 2.0, None, 0.0)
    text, _ = render_text(
        "blocks/irrigation_tech.j2",
        t=none,
        v=rounded(23.0),
        reel_width_m=60,
        reel_hose_m=400,
        small_area_ha=1,
    )
    assert "0 mm" not in " ".join(text) and "pokrywały" in text[0]
    strip = choose_technology(crops["potato"], 2.2, ParcelShape(950, 23, 1.0), 120.0)
    text, _ = render_text(
        "blocks/irrigation_tech.j2",
        t=strip,
        v=rounded(23.0),
        reel_width_m=60,
        reel_hose_m=400,
        small_area_ha=1,
    )
    joined = " ".join(text)
    assert "950 × 23 m" in joined.replace("\xa0", " ") and "ok. 23 m" in joined


def test_break_even_compares_unrounded_area() -> None:
    from app.analysis.economics import EconomicsStatus, IrrigationEconomics, Verdict
    from app.crops.economics import Range
    from app.report.texts import render_text

    e = IrrigationEconomics(
        EconomicsStatus.OK,
        Verdict.BORDERLINE,
        "reel",
        7.6,
        [],
        0.2,
        None,
        None,
        None,
        2000.0,
        Range(low=1000, high=2000),
        None,
        7.7,
        False,
    )

    class V:
        technology_pl = "Deszczownia szpulowa"
        mean_loss_pct = 20.0
        water_m3_ha = 2000.0
        benefit_zl_ha_low = 1000.0
        benefit_zl_ha_high = 2000.0
        cost_zl_ha_low = 1500.0
        cost_zl_ha_high = 2500.0
        break_even_area_ha = 7.5
        area_step = 0.5

    text, _ = render_text("blocks/irrigation_economics.j2", e=e, v=V(), crop="ziemniaki")
    assert "więcej niż ta działka" in " ".join(text)


def test_drip_coverage_card_does_not_mention_a_sprinkler() -> None:
    r = report_for(crop_id="field_vegetables")
    assert r.retention_plan is not None and r.water_plan is not None
    assert r.water_plan.technology == "drip"
    assert "z deszczowni" not in r.retention_plan.coverage.text_pl


def test_break_even_never_a_fake_zero() -> None:
    ie = report_for(crop_id="potato").irrigation_economics
    assert ie is not None and ie.break_even_area_ha is not None and ie.break_even_area_ha > 0
