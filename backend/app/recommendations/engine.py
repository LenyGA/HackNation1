"""Recommendation engine (plan step M4): complete assessment → ordered list of recommendations with evidence.

Pure, no I/O. CLAUDE.md rule 1 and 2:
- without a complete assessment the list is empty (the report then says why),
- every recommendation comes from a rule that checked values computed for this parcel and carries at least one
  number (with source and period) that triggered it; a rule without numeric evidence is dropped,
- order: retention → agrotechnics → irrigation, then the rule priority within the category.
"""

from collections.abc import Sequence

from app.analysis.assessment import Assessment
from app.analysis.context import AnalysisInputs
from app.core.models import Indicator
from app.recommendations.agrotech import AGROTECH_RULES
from app.recommendations.horizon import horizon
from app.recommendations.irrigation import IRRIGATION_RULES
from app.recommendations.models import CATEGORY_ORDER, Recommendation, Rule, RuleContext
from app.recommendations.retention import RETENTION_RULES
from app.recommendations.texts_pl import render

ALL_RULES: list[Rule] = [*RETENTION_RULES, *AGROTECH_RULES, *IRRIGATION_RULES]


def _dedupe(evidence: list[Indicator]) -> list[Indicator]:
    seen: set[str] = set()
    out: list[Indicator] = []
    for ind in evidence:
        if ind.key not in seen:
            seen.add(ind.key)
            out.append(ind)
    return out


def recommend(
    assessment: Assessment, inputs: AnalysisInputs, rules: Sequence[Rule] = ALL_RULES
) -> list[Recommendation]:
    if not assessment.complete or assessment.current is None:
        return []
    ctx = RuleContext(assessment=assessment, inputs=inputs)
    fired: list[tuple[Rule, Recommendation]] = []
    for rule in rules:
        if not rule.condition(ctx):
            continue
        evidence = _dedupe([i for i in rule.evidence(ctx) if i.value is not None])
        if not evidence:
            continue
        params = rule.params(ctx)
        title, text = render(rule.template_key, params)
        fired.append(
            (
                rule,
                Recommendation(
                    number=0,
                    id=rule.id,
                    category=rule.category,
                    priority=rule.priority,
                    template=rule.template_key,
                    title_pl=title,
                    text_pl=text,
                    params=params,
                    evidence=evidence,
                    locations=rule.locations(ctx),
                    horizon=horizon(rule.id, ctx),
                ),
            )
        )
    fired.sort(key=lambda fr: (CATEGORY_ORDER.index(fr[0].category), fr[0].priority, fr[0].id))
    return [rec.model_copy(update={"number": n}) for n, (_, rec) in enumerate(fired, start=1)]
