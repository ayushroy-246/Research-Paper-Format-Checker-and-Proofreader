"""
modules/grammar_checker.py
==========================
3-layer grammar & academic-style checker for the AI-Powered Research Paper Checker.

Public API
----------
    check_grammar(parsed_data: dict | list) -> list[dict]
    assemble_doc_from_spans(spans: list[dict]) -> dict

Layers
------
    Layer 1  –  Heuristics     (pure Python / regex, zero external deps)
    Layer 2  –  LanguageTool   (Java NLP, singleton, retry-once, graceful degradation)
    Layer 3  –  Academic style (original contribution)

Issue schema — every issue returned has exactly these keys
----------------------------------------------------------
    {
        "id":         str,               # e.g. "grammar-lt-MORFOLOGIK_RULE"
        "category":   "grammar",
        "severity":   "critical" | "warning" | "info",
        "page":       int | None,
        "snippet":    str | None,        # exact text fragment where issue was found
        "message":    str,
        "suggestion": str,
    }

Architecture notes
------------------
- check_grammar() iterates parsed_doc page-by-page so every issue carries an
  accurate page number from the source.  _find_page_for_snippet() is kept as a
  fallback for the LanguageTool layer where offset-based page lookup is needed.
- Singleton pattern: LanguageTool JVM is started once per session and reused.
  On first failure a single retry fires after a 2-second pause; on second
  failure _lt_failed is set and Layer 2 is silently skipped for the session.
- _normalize_for_grammar() runs once per page before all three layers, removing
  citations, equations, URLs, and DOIs to prevent false positives.
- NOISY_LT_RULE_IDS blocklist suppresses rules that fire constantly on
  technical/academic text.
- LanguageTool output is capped at _LT_MAX_ISSUES (12) per page.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NOISY_LT_RULE_IDS: set[str] = {
    "WHITESPACE_RULE",
    "DOUBLE_PUNCTUATION",
    "COMMA_PARENTHESIS_WHITESPACE",
    "EN_QUOTES",
    "DASH_RULE",
    "UPPERCASE_SENTENCE_START",
    "PUNCTUATION_PARAGRAPH_END",
    "SENTENCE_WHITESPACE",
    "MORFOLOGIK_RULE_EN_US",
    "EN_UNPAIRED_BRACKETS",
    "ARROWS",
    "UNLIKELY_OPENING_PUNCTUATION",
    "REPEATED_WORDS_3X",
}

# Normalizer compiled patterns
_REF_SECTION_RE   = re.compile(r'\b(references|bibliography)\b.*',
                                re.IGNORECASE | re.DOTALL)
_DOI_RE           = re.compile(r'\bdoi:\s*\S+', re.IGNORECASE)
_URL_RE           = re.compile(r'https?://\S+')
_EQUATION_RE      = re.compile(r'\$[^$]+\$|\\\([^)]+\\\)|\\\[[^\]]+\\\]')
_CITATION_TAG_RE  = re.compile(r'\[[\d,\-\s]+\]|\([A-Za-z\s]+,\s\d{4}\)')
_TABLE_CAPTION_RE = re.compile(r'\b(table|figure|fig\.?)\s+\d+', re.IGNORECASE)
_MATH_TOKENS_RE   = re.compile(r'[=<>≤≥±×÷∑∫∂√∞]')

# Layer 1 – heuristic patterns
_REPEATED_WORD_RE = re.compile(r'\b(\w+)\s+\1\b', re.IGNORECASE)
_REPEATED_WORD_ALLOWLIST: set[str] = {"had", "that"}

_CONTRACTION_RE = re.compile(
    r"\b(can't|won't|don't|doesn't|didn't|isn't|aren't|wasn't|weren't|"
    r"it's|i'm|i've|i'd|i'll|we're|we've|we'd|we'll|you're|they're|"
    r"he's|she's|that's|there's|here's|let's|who's|what's)\b",
    re.IGNORECASE,
)
_CONTRACTION_EXPANSIONS: dict[str, str] = {
    "can't":   "cannot",
    "won't":   "will not",
    "don't":   "do not",
    "doesn't": "does not",
    "didn't":  "did not",
    "isn't":   "is not",
    "aren't":  "are not",
    "wasn't":  "was not",
    "weren't": "were not",
    "it's":    "it is / its",
    "i'm":     "I am",
    "i've":    "I have",
    "i'd":     "I would / I had",
    "i'll":    "I will",
    "we're":   "we are",
    "we've":   "we have",
    "we'd":    "we would / we had",
    "we'll":   "we will",
    "you're":  "you are",
    "they're": "they are",
    "he's":    "he is / he has",
    "she's":   "she is / she has",
    "that's":  "that is / that has",
    "there's": "there is / there has",
    "here's":  "here is",
    "let's":   "let us",
    "who's":   "who is / who has",
    "what's":  "what is / what has",
}

_FIRST_PERSON_RE = re.compile(r'\b(I|me|my|myself|we|our|ours|ourselves)\b')

# Layer 3 – academic style patterns
_SUBJECTIVE_FP_RE = re.compile(
    r'\b(I believe|In my opinion|As I have shown|I think|I feel|'
    r'In my view|I argue that|I claim that)\b',
    re.IGNORECASE,
)
_OVERCONFIDENT_RE = re.compile(
    r'\b(proves?|guarantees?|demonstrates? conclusively|shows? definitively|'
    r'undeniably|certainly|it is clear that|clearly shows?|obviously|'
    r'without (any )?doubt|it is evident that|unquestionably)\b',
    re.IGNORECASE,
)
_SUPERLATIVE_RE = re.compile(
    r'\b(the\s+)?(best|worst|fastest|slowest|most\s+accurate|most\s+efficient|'
    r'most\s+effective|most\s+advanced|state-of-the-art|unprecedented|'
    r'superior to all|outperforms? all|novel(?!\w))\b',
    re.IGNORECASE,
)
_VAGUE_QUANTIFIER_RE = re.compile(
    r'\b(many|few|several|some|a number of|various|numerous|a lot of|'
    r'most|majority of|large amount of|small amount of)\b',
    re.IGNORECASE,
)
_MISSING_HEDGE_RE = re.compile(
    r'\b(this\s+(model|method|approach|system|algorithm|framework|technique)'
    r'\s+(is|works|performs|achieves|provides|yields|produces|improves))\b',
    re.IGNORECASE,
)
_HEDGE_WORDS_RE = re.compile(
    r'\b(suggests?|indicates?|appears?\s+to|seems?\s+to|may|might|could|'
    r'is likely|tends?\s+to|is expected to)\b',
    re.IGNORECASE,
)
_ACTIVE_PASSIVE_RE = re.compile(
    r'\b(we\s+(found|observed|note|conclude|believe|claim|argue|show|propose|'
    r'present|demonstrate|evaluate|compare|analyse|analyze))\b',
    re.IGNORECASE,
)
_METHOD_RESULT_KWS_RE = re.compile(
    r'\b(experiment|evaluation|dataset|baseline|results?|training|testing|'
    r'validation|accuracy|performance|benchmark)\b',
    re.IGNORECASE,
)

_LT_MAX_ISSUES = 12

# ---------------------------------------------------------------------------
# Module-level singleton state
# ---------------------------------------------------------------------------
_lt_tool: Any | None = None
_lt_failed: bool = False


# ===========================================================================
# Private helpers
# ===========================================================================

def _build_issue(
    *,
    id: str,
    severity: str,
    page: int | None,
    snippet: str | None,        # ← NEW: the exact text fragment flagged
    message: str,
    suggestion: str,
) -> dict:
    """
    Construct a validated issue dict.
    Single source of truth for the issue schema — all layers call this.
    snippet is trimmed to 120 chars max so it stays readable in the UI.
    """
    if snippet:
        snippet = snippet.strip()[:120]
    return {
        "id":         id,
        "category":   "grammar",
        "severity":   severity,
        "page":       page,
        "snippet":    snippet,
        "message":    message,
        "suggestion": suggestion,
    }


def _get_tool():
    """Return the LanguageTool singleton (retry-once on failure)."""
    global _lt_tool, _lt_failed

    if _lt_failed:
        return None
    if _lt_tool is not None:
        return _lt_tool

    import time

    for attempt in (1, 2):
        try:
            import language_tool_python    # noqa: PLC0415
            logger.info(
                "[INFO] Starting LanguageTool Java Server (attempt %d/2)...", attempt
            )
            _lt_tool = language_tool_python.LanguageTool("en-US")
            logger.info("[INFO] LanguageTool ready.")
            return _lt_tool
        except Exception as exc:           # noqa: BLE001
            logger.warning(
                "[ERROR] LanguageTool attempt %d/2 failed: %s", attempt, exc
            )
            if attempt == 1:
                time.sleep(2)

    _lt_failed = True
    logger.warning(
        "[ERROR] LanguageTool unavailable after 2 attempts -- "
        "Layer 2 will be skipped for the remainder of this session."
    )
    return None


def _find_page_for_snippet(snippet: str, parsed_doc: dict) -> int | None:
    """Fallback page locator: scans all pages for the first one containing snippet."""
    if not snippet or not isinstance(parsed_doc, dict):
        return None
    snippet_lower = snippet.lower().strip()
    for page in parsed_doc.get("pages", []):
        if snippet_lower in (page.get("text") or "").lower():
            return page.get("page_number")
    return None


def _normalize_for_grammar(text: str) -> str:
    """Strip non-prose content (refs, equations, URLs, citations) before analysis."""
    text = _REF_SECTION_RE.sub(" ", text)
    text = _DOI_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    text = _EQUATION_RE.sub(" ", text)
    text = _CITATION_TAG_RE.sub(" ", text)
    text = _TABLE_CAPTION_RE.sub(" ", text)
    text = _MATH_TOKENS_RE.sub(" ", text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


# ===========================================================================
# Layer 1 – Heuristic checks
# ===========================================================================

def _heuristic_checks(text: str, page: int | None) -> list[dict]:
    issues: list[dict] = []

    # 1. Repeated words
    for match in _REPEATED_WORD_RE.finditer(text):
        word = match.group(1).lower()
        if word in _REPEATED_WORD_ALLOWLIST:
            continue
        issues.append(_build_issue(
            id         = "grammar-heuristic-repeated-word",
            severity   = "warning",
            page       = page,
            snippet    = match.group(0),            # e.g. "the the"
            message    = f"Repeated word detected: '{word} {word}'.",
            suggestion = f"Remove one occurrence of '{word}'.",
        ))

    # 2. Long sentences
    for sentence in re.split(r'(?<=[.?!])\s+', text):
        words = sentence.split()
        if len(words) > 45:
            # Show first 100 chars of the sentence as the locator snippet
            issues.append(_build_issue(
                id         = "grammar-heuristic-long-sentence",
                severity   = "info",
                page       = page,
                snippet    = sentence[:100],
                message    = f"Sentence is {len(words)} words long (recommended max: 45).",
                suggestion = "Break into two or more shorter sentences for clarity.",
            ))

    # 3. Contractions
    seen_contractions: set[str] = set()
    for match in _CONTRACTION_RE.finditer(text):
        form = match.group(0).lower()
        if form in seen_contractions:
            continue
        seen_contractions.add(form)
        expansion = _CONTRACTION_EXPANSIONS.get(form, "full form")
        issues.append(_build_issue(
            id         = "grammar-heuristic-contraction",
            severity   = "warning",
            page       = page,
            snippet    = match.group(0),            # e.g. "can't"
            message    = f"Informal contraction '{match.group(0)}' is inappropriate in academic writing.",
            suggestion = f"Expand to '{expansion}'.",
        ))

    # 4. First-person pronouns
    seen_fp: set[str] = set()
    for match in _FIRST_PERSON_RE.finditer(text):
        token = match.group(0).lower()
        if token in seen_fp:
            continue
        seen_fp.add(token)
        issues.append(_build_issue(
            id         = "grammar-heuristic-first-person",
            severity   = "warning",
            page       = page,
            snippet    = match.group(0),            # e.g. "We"
            message    = f"First-person pronoun '{match.group(0)}' found.",
            suggestion = (
                "Use passive voice or third-person constructions "
                "(e.g. 'The experiment was conducted...' instead of 'We conducted...')."
            ),
        ))

    return issues


# ===========================================================================
# Layer 2 – LanguageTool
# ===========================================================================

def _languagetool_checks(text: str, page: int | None) -> list[dict]:
    tool = _get_tool()
    if tool is None:
        return []

    try:
        matches = tool.check(text)
    except Exception as exc:
        logger.warning("grammar_checker: LanguageTool.check() failed: %s", exc)
        return []

    issues: list[dict] = []
    for match in matches:
        if len(issues) >= _LT_MAX_ISSUES:
            break

        rule_id = getattr(match, "ruleId", "") or "general"
        if rule_id in NOISY_LT_RULE_IDS:
            continue

        issue_type = getattr(match, "ruleIssueType", "") or ""
        severity   = "critical" if issue_type == "misspelling" else "warning"

        replacements = getattr(match, "replacements", []) or []
        suggestion   = (
            f"Try: {', '.join(replacements[:2])}"
            if replacements
            else "Review sentence structure."
        )

        # Extract the exact flagged token from LT's context + offset
        context  = getattr(match, "context", "") or ""
        offset   = getattr(match, "offsetInContext", 0) or 0
        length   = getattr(match, "errorLength", 1) or 1
        snippet  = context[offset: offset + length].strip() if context else None

        issues.append(_build_issue(
            id         = f"grammar-lt-{rule_id.lower()}",
            severity   = severity,
            page       = page,
            snippet    = snippet,                   # e.g. "recieve"
            message    = getattr(match, "message", "LanguageTool flagged an issue."),
            suggestion = suggestion,
        ))

    return issues


# ===========================================================================
# Layer 3 – Academic style checks
# ===========================================================================

def _academic_style_checks(text: str, page: int | None) -> list[dict]:
    issues: list[dict] = []

    # 1. Subjective first-person phrases
    seen_sfp: set[str] = set()
    for match in _SUBJECTIVE_FP_RE.finditer(text):
        token = match.group(0).lower()
        if token in seen_sfp:
            continue
        seen_sfp.add(token)
        issues.append(_build_issue(
            id         = "grammar-style-subjective-first-person",
            severity   = "warning",
            page       = page,
            snippet    = match.group(0),            # e.g. "I believe"
            message    = f"Subjective first-person phrasing: '{match.group(0)}'.",
            suggestion = "Rewrite objectively (e.g. 'The results indicate...').",
        ))

    # 2. Overconfident claims
    seen_oc: set[str] = set()
    for match in _OVERCONFIDENT_RE.finditer(text):
        token = match.group(0).lower()
        if token in seen_oc:
            continue
        seen_oc.add(token)
        issues.append(_build_issue(
            id         = "grammar-academic-overconfident-claim",
            severity   = "critical",
            page       = page,
            snippet    = match.group(0),            # e.g. "clearly shows"
            message    = (
                f"Overconfident language: '{match.group(0)}'. "
                "Academic claims must be appropriately qualified."
            ),
            suggestion = (
                "Replace with hedged language such as 'suggests', 'indicates', "
                "'appears to', or 'may demonstrate'."
            ),
        ))

    # 3. Unsupported superlatives
    seen_sup: set[str] = set()
    for match in _SUPERLATIVE_RE.finditer(text):
        token = match.group(0).lower().strip()
        if token in seen_sup:
            continue
        seen_sup.add(token)
        issues.append(_build_issue(
            id         = "grammar-academic-unsupported-superlative",
            severity   = "warning",
            page       = page,
            snippet    = match.group(0).strip(),    # e.g. "the best"
            message    = (
                f"Superlative or absolute claim: '{match.group(0).strip()}'. "
                "This requires explicit comparative evidence or a citation."
            ),
            suggestion = (
                "Either cite evidence for the claim or use a relative comparative "
                "(e.g. 'outperforms the baseline' instead of 'the best')."
            ),
        ))

    # 4. Vague quantifiers
    seen_vq: set[str] = set()
    for match in _VAGUE_QUANTIFIER_RE.finditer(text):
        token = match.group(0).lower()
        if token in seen_vq:
            continue
        seen_vq.add(token)
        issues.append(_build_issue(
            id         = "grammar-academic-vague-quantifier",
            severity   = "info",
            page       = page,
            snippet    = match.group(0),            # e.g. "many"
            message    = f"Vague quantifier '{match.group(0)}' lacks precision.",
            suggestion = (
                "Replace with a specific number or percentage where possible "
                "(e.g. '47 participants' instead of 'many participants')."
            ),
        ))

    # 5. Missing hedging
    for match in _MISSING_HEDGE_RE.finditer(text):
        start  = max(0, match.start() - 60)
        end    = min(len(text), match.end() + 60)
        window = text[start:end]
        if not _HEDGE_WORDS_RE.search(window):
            issues.append(_build_issue(
                id         = "grammar-academic-missing-hedge",
                severity   = "warning",
                page       = page,
                snippet    = match.group(0),        # e.g. "this method performs"
                message    = (
                    f"Unhedged claim: '{match.group(0)}'. "
                    "Direct assertions without qualification are discouraged."
                ),
                suggestion = (
                    "Add hedging language, e.g. 'This method appears to...' "
                    "or 'The proposed approach may...'."
                ),
            ))

    # 6. Active voice in methods / results context
    seen_av: set[str] = set()
    for match in _ACTIVE_PASSIVE_RE.finditer(text):
        phrase = match.group(0).lower()
        if phrase in seen_av:
            continue
        sent_start = text.rfind('.', 0, match.start()) + 1
        sent_end   = text.find('.', match.end())
        if sent_end == -1:
            sent_end = len(text)
        sentence = text[sent_start:sent_end]
        if _METHOD_RESULT_KWS_RE.search(sentence):
            seen_av.add(phrase)
            issues.append(_build_issue(
                id         = "grammar-academic-active-voice-methods",
                severity   = "info",
                page       = page,
                snippet    = match.group(0),        # e.g. "we found"
                message    = (
                    f"Active voice ('{match.group(0)}') in a methods/results context. "
                    "Many venues prefer passive construction here."
                ),
                suggestion = (
                    "Consider passive voice, e.g. "
                    "'Experiments were conducted...' instead of 'We conducted...'."
                ),
            ))

    return issues


# ===========================================================================
# Data Assembler (Bridge from pdf_ingestion)
# ===========================================================================

def assemble_doc_from_spans(spans: list[dict]) -> dict:
    """
    BRIDGE FUNCTION:
    Converts the 'List of Spans' from pdf_ingestion.py into the
    'Page-based Dict' required by check_grammar().
    """
    pages_map: dict[int, list[str]] = {}

    for span in spans:
        p_num = span.get("page", 1)
        text  = span.get("text", "")
        if p_num not in pages_map:
            pages_map[p_num] = []
        pages_map[p_num].append(text)

    return {
        "pages": [
            {"page_number": p_num, "text": " ".join(pages_map[p_num])}
            for p_num in sorted(pages_map.keys())
        ]
    }


# ===========================================================================
# Public API
# ===========================================================================

def check_grammar(parsed_data: dict | list) -> list[dict]:
    """
    Main entry point -- called by app.py / the central orchestrator.

    Parameters
    ----------
    parsed_data : dict | list
        If passed a dict, assumes it is already formatted into pages.
        If passed a list, assumes it is the raw 'span' output from
        pdf_ingestion.py and automatically assembles it via
        assemble_doc_from_spans().

    Returns
    -------
    list[dict]
        Aggregated issue list across all pages.
        Every issue contains: id, category, severity, page, snippet,
        message, suggestion.
    """
    all_issues: list[dict] = []

    # Auto-detect input format
    if isinstance(parsed_data, list):
        parsed_doc = assemble_doc_from_spans(parsed_data)
        logger.info(
            "Auto-assembled %d spans into %d pages.",
            len(parsed_data), len(parsed_doc.get("pages", []))
        )
    else:
        parsed_doc = parsed_data

    if not parsed_doc or "pages" not in parsed_doc:
        logger.warning("grammar_checker.check_grammar: empty or malformed parsed_doc.")
        return all_issues

    for page_data in parsed_doc.get("pages", []):
        page_num = page_data.get("page_number")
        raw_text = page_data.get("text", "") or ""

        if not raw_text.strip():
            continue

        clean_text = _normalize_for_grammar(raw_text)

        # --- Layer 1 ---
        try:
            layer1 = _heuristic_checks(clean_text, page_num)
            logger.debug("Page %s | Layer 1: %d issues.", page_num, len(layer1))
            all_issues.extend(layer1)
        except Exception as exc:
            logger.error("Page %s | Layer 1 crashed: %s", page_num, exc, exc_info=True)

        # --- Layer 2 ---
        try:
            layer2 = _languagetool_checks(clean_text, page_num)
            logger.debug("Page %s | Layer 2: %d issues.", page_num, len(layer2))
            all_issues.extend(layer2)
        except Exception as exc:
            logger.error("Page %s | Layer 2 crashed: %s", page_num, exc, exc_info=True)

        # --- Layer 3 ---
        try:
            layer3 = _academic_style_checks(clean_text, page_num)
            logger.debug("Page %s | Layer 3: %d issues.", page_num, len(layer3))
            all_issues.extend(layer3)
        except Exception as exc:
            logger.error("Page %s | Layer 3 crashed: %s", page_num, exc, exc_info=True)

    logger.info("grammar_checker: %d total issues across all pages.", len(all_issues))
    return all_issues