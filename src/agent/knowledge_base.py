"""
Knowledge base search over product-docs.md.
Uses keyword matching in the prototype; will be replaced with
vector/semantic search (pgvector) in Stage 2.
"""

import re
from pathlib import Path
from dataclasses import dataclass


DOCS_PATH = Path(__file__).parents[2] / "context" / "product-docs.md"


@dataclass
class SearchResult:
    section: str
    content: str
    score: float


def _load_sections() -> list[tuple[str, str]]:
    """Parse product-docs.md into (heading, body) tuples."""
    text = DOCS_PATH.read_text(encoding="utf-8")
    sections = []
    current_heading = "General"
    current_body: list[str] = []

    for line in text.splitlines():
        if line.startswith("## ") or line.startswith("### "):
            if current_body:
                sections.append((current_heading, "\n".join(current_body).strip()))
            current_heading = line.lstrip("#").strip()
            current_body = []
        else:
            current_body.append(line)

    if current_body:
        sections.append((current_heading, "\n".join(current_body).strip()))

    return sections


# load once at module import
_SECTIONS = _load_sections()

# keyword synonyms to improve recall
_SYNONYMS: dict[str, list[str]] = {
    "email": ["gmail", "outlook", "inbox", "smtp", "sync"],
    "password": ["login", "sign in", "access", "credentials", "reset"],
    "billing": ["invoice", "charge", "payment", "subscription", "plan", "cost", "price"],
    "contact": ["lead", "client", "customer", "prospect"],
    "pipeline": ["deal", "stage", "kanban", "board"],
    "automation": ["drip", "sequence", "trigger", "workflow"],
    "integration": ["connect", "sync", "zillow", "realtor", "docusign", "zapier", "calendar"],
    "mobile": ["app", "ios", "android", "iphone", "phone"],
    "export": ["download", "csv", "backup", "data"],
    "team": ["agent", "member", "invite", "role", "permission"],
    "transaction": ["closing", "escrow", "checklist", "contract", "offer"],
    "whatsapp": ["sms", "text", "message", "twilio"],
}


def _expand_query(query: str) -> set[str]:
    """Expand query terms with synonyms."""
    tokens = set(re.findall(r'\w+', query.lower()))
    expanded = set(tokens)
    for token in tokens:
        if token in _SYNONYMS:
            expanded.update(_SYNONYMS[token])
        for key, synonyms in _SYNONYMS.items():
            if token in synonyms:
                expanded.add(key)
                expanded.update(synonyms)
    return expanded


def _score(heading: str, body: str, terms: set[str]) -> float:
    """Score a section by how many query terms appear in it."""
    text = (heading + " " + body).lower()
    words = set(re.findall(r'\w+', text))
    hits = terms & words
    # heading matches count double
    heading_words = set(re.findall(r'\w+', heading.lower()))
    heading_hits = terms & heading_words
    return len(hits) + len(heading_hits)


def search(query: str, max_results: int = 3) -> list[SearchResult]:
    """
    Search the knowledge base for sections relevant to the query.
    Returns up to max_results sections, ordered by relevance.
    """
    terms = _expand_query(query)
    scored = []

    for heading, body in _SECTIONS:
        score = _score(heading, body, terms)
        if score > 0:
            # trim body to 600 chars for context window efficiency
            snippet = body[:600] + ("..." if len(body) > 600 else "")
            scored.append(SearchResult(section=heading, content=snippet, score=score))

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:max_results]


def format_results(results: list[SearchResult]) -> str:
    """Format search results as a readable string for the agent prompt."""
    if not results:
        return "No relevant documentation found."
    parts = []
    for r in results:
        parts.append(f"### {r.section}\n{r.content}")
    return "\n\n---\n\n".join(parts)
