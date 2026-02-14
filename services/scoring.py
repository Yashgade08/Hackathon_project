import math
import time

from app.models import AnalysisResult, TrendItem
from app.services.verifier import verify_claim

SENSATIONAL_KEYWORDS = {
    "shocking",
    "must watch",
    "rumor",
    "unverified",
    "leaked",
    "explodes",
    "you won't believe",
    "viral",
    "breaking",
}


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    return max(min_val, min(max_val, value))


def _language_risk(title: str) -> float:
    lower = title.lower()
    keyword_hits = sum(1 for k in SENSATIONAL_KEYWORDS if k in lower)
    exclamation_risk = 0.15 if "!" in title else 0.0
    caps_words = [w for w in title.split() if len(w) > 4 and w.isupper()]
    caps_risk = min(0.2, len(caps_words) * 0.05)
    return _clamp(keyword_hits * 0.08 + exclamation_risk + caps_risk)


def _spread_index(trend: TrendItem) -> float:
    score = float(trend.metrics.get("score", 0))
    comments = float(trend.metrics.get("comments", 0))
    engagement = float(trend.metrics.get("engagement", score + comments))
    hours_old = max(1.0, (time.time() - float(trend.created_utc)) / 3600.0)
    velocity = engagement / hours_old
    # Saturating transform for readability on a 0-100 scale.
    spread = 100.0 * (1 - math.exp(-velocity / 120.0))
    return round(_clamp(spread / 100.0) * 100, 2)


def analyze_trend(trend: TrendItem) -> AnalysisResult:
    evidence = verify_claim(trend.title)
    language_risk = _language_risk(trend.title)
    verification_strength = evidence.confidence
    spread_index = _spread_index(trend)

    fake_probability = _clamp(
        0.82
        - (verification_strength * 0.72)
        - (min(evidence.credible_hits, 4) * 0.05)
        + (language_risk * 0.35)
    )
    credibility_score = _clamp(1.0 - fake_probability)

    reasons: list[str] = []
    if evidence.credible_hits >= 3:
        reasons.append("Multiple high-trust outlets reported similar claims.")
    elif evidence.credible_hits == 0:
        reasons.append("No high-trust corroboration found in top results.")
    else:
        reasons.append("Partial corroboration from trusted outlets.")

    if evidence.source_diversity <= 1:
        reasons.append("Low source diversity increases uncertainty.")
    if language_risk >= 0.2:
        reasons.append("Headline wording appears potentially sensational.")
    if spread_index >= 70:
        reasons.append("High social velocity suggests rapid spread.")

    if fake_probability <= 0.25:
        verdict = "Likely Real"
    elif fake_probability <= 0.55:
        verdict = "Needs Verification"
    else:
        verdict = "Likely Misleading"

    return AnalysisResult(
        trend=trend,
        fake_probability=round(fake_probability * 100, 2),
        spread_index=spread_index,
        credibility_score=round(credibility_score * 100, 2),
        verdict=verdict,
        reasons=reasons,
        evidence=evidence,
    )
