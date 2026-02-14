from typing import Any

from pydantic import BaseModel, Field


class TrendItem(BaseModel):
    id: str
    platform: str
    title: str
    url: str
    author: str = "unknown"
    created_utc: int
    metrics: dict[str, Any] = Field(default_factory=dict)


class EvidenceArticle(BaseModel):
    title: str
    source: str
    source_url: str
    article_url: str
    published_at: str
    source_weight: float


class VerificationEvidence(BaseModel):
    query: str
    credible_hits: int
    total_hits: int
    source_diversity: int
    confidence: float
    articles: list[EvidenceArticle] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    trend: TrendItem
    fake_probability: float
    spread_index: float
    credibility_score: float
    verdict: str
    reasons: list[str]
    evidence: VerificationEvidence


class AnalyzeResponse(BaseModel):
    generated_at: str
    analyzed_count: int
    results: list[AnalysisResult]
