# # """
# # modules/grammar_checker.py
# # ==========================
# # 3-layer grammar & academic-style checker for the AI-Powered Research Paper Checker.

# # Public API
# # ----------
# #     check_grammar(parsed_data: dict | list) -> list[dict]
# #     assemble_doc_from_spans(spans: list[dict]) -> dict

# # Layers
# # ------
# #     Layer 1  –  Heuristics     (pure Python / regex, zero external deps)
# #     Layer 2  –  LanguageTool   (Java NLP, singleton, retry-once, graceful degradation)
# #     Layer 3  –  Academic style (original contribution)

# # Issue schema — every issue returned has exactly these keys
# # ----------------------------------------------------------
# #     {
# #         "id":         str,               # e.g. "grammar-lt-MORFOLOGIK_RULE"
# #         "category":   "grammar",
# #         "severity":   "critical" | "warning" | "info",
# #         "page":       int | None,
# #         "snippet":    str | None,        # exact text fragment where issue was found
# #         "message":    str,
# #         "suggestion": str,
# #     }

# # Architecture notes
# # ------------------
# # - check_grammar() iterates parsed_doc page-by-page so every issue carries an
# #   accurate page number from the source.  _find_page_for_snippet() is kept as a
# #   fallback for the LanguageTool layer where offset-based page lookup is needed.
# # - Singleton pattern: LanguageTool JVM is started once per session and reused.
# #   On first failure a single retry fires after a 2-second pause; on second
# #   failure _lt_failed is set and Layer 2 is silently skipped for the session.
# # - _normalize_for_grammar() runs once per page before all three layers, removing
# #   citations, equations, URLs, and DOIs to prevent false positives.
# # - NOISY_LT_RULE_IDS blocklist suppresses rules that fire constantly on
# #   technical/academic text.
# # - LanguageTool output is capped at _LT_MAX_ISSUES (12) per page.
# # """

# # from __future__ import annotations

# # import logging
# # import re
# # from typing import Any

# # logger = logging.getLogger(__name__)

# # # ---------------------------------------------------------------------------
# # # Constants
# # # ---------------------------------------------------------------------------

# # NOISY_LT_RULE_IDS: set[str] = {
# #     "WHITESPACE_RULE",
# #     "DOUBLE_PUNCTUATION",
# #     "COMMA_PARENTHESIS_WHITESPACE",
# #     "EN_QUOTES",
# #     "DASH_RULE",
# #     "UPPERCASE_SENTENCE_START",
# #     "PUNCTUATION_PARAGRAPH_END",
# #     "SENTENCE_WHITESPACE",
# #     "MORFOLOGIK_RULE_EN_US",
# #     "EN_UNPAIRED_BRACKETS",
# #     "ARROWS",
# #     "UNLIKELY_OPENING_PUNCTUATION",
# #     "REPEATED_WORDS_3X",
# # }

# # # Normalizer compiled patterns
# # _REF_SECTION_RE   = re.compile(r'\b(references|bibliography)\b.*',
# #                                 re.IGNORECASE | re.DOTALL)
# # _DOI_RE           = re.compile(r'\bdoi:\s*\S+', re.IGNORECASE)
# # _URL_RE           = re.compile(r'https?://\S+')
# # _EQUATION_RE      = re.compile(r'\$[^$]+\$|\\\([^)]+\\\)|\\\[[^\]]+\\\]')
# # _CITATION_TAG_RE  = re.compile(r'\[[\d,\-\s]+\]|\([A-Za-z\s]+,\s\d{4}\)')
# # _TABLE_CAPTION_RE = re.compile(r'\b(table|figure|fig\.?)\s+\d+', re.IGNORECASE)
# # _MATH_TOKENS_RE   = re.compile(r'[=<>≤≥±×÷∑∫∂√∞]')

# # # Layer 1 – heuristic patterns
# # _REPEATED_WORD_RE = re.compile(r'\b(\w+)\s+\1\b', re.IGNORECASE)
# # _REPEATED_WORD_ALLOWLIST: set[str] = {"had", "that"}

# # _CONTRACTION_RE = re.compile(
# #     r"\b(can't|won't|don't|doesn't|didn't|isn't|aren't|wasn't|weren't|"
# #     r"it's|i'm|i've|i'd|i'll|we're|we've|we'd|we'll|you're|they're|"
# #     r"he's|she's|that's|there's|here's|let's|who's|what's)\b",
# #     re.IGNORECASE,
# # )
# # _CONTRACTION_EXPANSIONS: dict[str, str] = {
# #     "can't":   "cannot",
# #     "won't":   "will not",
# #     "don't":   "do not",
# #     "doesn't": "does not",
# #     "didn't":  "did not",
# #     "isn't":   "is not",
# #     "aren't":  "are not",
# #     "wasn't":  "was not",
# #     "weren't": "were not",
# #     "it's":    "it is / its",
# #     "i'm":     "I am",
# #     "i've":    "I have",
# #     "i'd":     "I would / I had",
# #     "i'll":    "I will",
# #     "we're":   "we are",
# #     "we've":   "we have",
# #     "we'd":    "we would / we had",
# #     "we'll":   "we will",
# #     "you're":  "you are",
# #     "they're": "they are",
# #     "he's":    "he is / he has",
# #     "she's":   "she is / she has",
# #     "that's":  "that is / that has",
# #     "there's": "there is / there has",
# #     "here's":  "here is",
# #     "let's":   "let us",
# #     "who's":   "who is / who has",
# #     "what's":  "what is / what has",
# # }

# # _FIRST_PERSON_RE = re.compile(r'\b(I|me|my|myself|we|our|ours|ourselves)\b')

# # # Layer 3 – academic style patterns
# # _SUBJECTIVE_FP_RE = re.compile(
# #     r'\b(I believe|In my opinion|As I have shown|I think|I feel|'
# #     r'In my view|I argue that|I claim that)\b',
# #     re.IGNORECASE,
# # )
# # _OVERCONFIDENT_RE = re.compile(
# #     r'\b(proves?|guarantees?|demonstrates? conclusively|shows? definitively|'
# #     r'undeniably|certainly|it is clear that|clearly shows?|obviously|'
# #     r'without (any )?doubt|it is evident that|unquestionably)\b',
# #     re.IGNORECASE,
# # )
# # _SUPERLATIVE_RE = re.compile(
# #     r'\b(the\s+)?(best|worst|fastest|slowest|most\s+accurate|most\s+efficient|'
# #     r'most\s+effective|most\s+advanced|state-of-the-art|unprecedented|'
# #     r'superior to all|outperforms? all|novel(?!\w))\b',
# #     re.IGNORECASE,
# # )
# # _VAGUE_QUANTIFIER_RE = re.compile(
# #     r'\b(many|few|several|some|a number of|various|numerous|a lot of|'
# #     r'most|majority of|large amount of|small amount of)\b',
# #     re.IGNORECASE,
# # )
# # _MISSING_HEDGE_RE = re.compile(
# #     r'\b(this\s+(model|method|approach|system|algorithm|framework|technique)'
# #     r'\s+(is|works|performs|achieves|provides|yields|produces|improves))\b',
# #     re.IGNORECASE,
# # )
# # _HEDGE_WORDS_RE = re.compile(
# #     r'\b(suggests?|indicates?|appears?\s+to|seems?\s+to|may|might|could|'
# #     r'is likely|tends?\s+to|is expected to)\b',
# #     re.IGNORECASE,
# # )
# # _ACTIVE_PASSIVE_RE = re.compile(
# #     r'\b(we\s+(found|observed|note|conclude|believe|claim|argue|show|propose|'
# #     r'present|demonstrate|evaluate|compare|analyse|analyze))\b',
# #     re.IGNORECASE,
# # )
# # _METHOD_RESULT_KWS_RE = re.compile(
# #     r'\b(experiment|evaluation|dataset|baseline|results?|training|testing|'
# #     r'validation|accuracy|performance|benchmark)\b',
# #     re.IGNORECASE,
# # )

# # _LT_MAX_ISSUES = 12

# # # ---------------------------------------------------------------------------
# # # Module-level singleton state
# # # ---------------------------------------------------------------------------
# # _lt_tool: Any | None = None
# # _lt_failed: bool = False


# # # ===========================================================================
# # # Private helpers
# # # ===========================================================================

# # def _build_issue(
# #     *,
# #     id: str,
# #     severity: str,
# #     page: int | None,
# #     snippet: str | None,        # ← NEW: the exact text fragment flagged
# #     message: str,
# #     suggestion: str,
# # ) -> dict:
# #     """
# #     Construct a validated issue dict.
# #     Single source of truth for the issue schema — all layers call this.
# #     snippet is trimmed to 120 chars max so it stays readable in the UI.
# #     """
# #     if snippet:
# #         snippet = snippet.strip()[:120]
# #     return {
# #         "id":         id,
# #         "category":   "grammar",
# #         "severity":   severity,
# #         "page":       page,
# #         "snippet":    snippet,
# #         "message":    message,
# #         "suggestion": suggestion,
# #     }


# # def _get_tool():
# #     """Return the LanguageTool singleton (retry-once on failure)."""
# #     global _lt_tool, _lt_failed

# #     if _lt_failed:
# #         return None
# #     if _lt_tool is not None:
# #         return _lt_tool

# #     import time

# #     for attempt in (1, 2):
# #         try:
# #             import language_tool_python    # noqa: PLC0415
# #             logger.info(
# #                 "[INFO] Starting LanguageTool Java Server (attempt %d/2)...", attempt
# #             )
# #             _lt_tool = language_tool_python.LanguageTool("en-US")
# #             logger.info("[INFO] LanguageTool ready.")
# #             return _lt_tool
# #         except Exception as exc:           # noqa: BLE001
# #             logger.warning(
# #                 "[ERROR] LanguageTool attempt %d/2 failed: %s", attempt, exc
# #             )
# #             if attempt == 1:
# #                 time.sleep(2)

# #     _lt_failed = True
# #     logger.warning(
# #         "[ERROR] LanguageTool unavailable after 2 attempts -- "
# #         "Layer 2 will be skipped for the remainder of this session."
# #     )
# #     return None


# # def _find_page_for_snippet(snippet: str, parsed_doc: dict) -> int | None:
# #     """Fallback page locator: scans all pages for the first one containing snippet."""
# #     if not snippet or not isinstance(parsed_doc, dict):
# #         return None
# #     snippet_lower = snippet.lower().strip()
# #     for page in parsed_doc.get("pages", []):
# #         if snippet_lower in (page.get("text") or "").lower():
# #             return page.get("page_number")
# #     return None


# # def _normalize_for_grammar(text: str) -> str:
# #     """Strip non-prose content (refs, equations, URLs, citations) before analysis."""
# #     text = _REF_SECTION_RE.sub(" ", text)
# #     text = _DOI_RE.sub(" ", text)
# #     text = _URL_RE.sub(" ", text)
# #     text = _EQUATION_RE.sub(" ", text)
# #     text = _CITATION_TAG_RE.sub(" ", text)
# #     text = _TABLE_CAPTION_RE.sub(" ", text)
# #     text = _MATH_TOKENS_RE.sub(" ", text)
# #     text = re.sub(r'[ \t]{2,}', ' ', text)
# #     return text.strip()


# # # ===========================================================================
# # # Layer 1 – Heuristic checks
# # # ===========================================================================

# # def _heuristic_checks(text: str, page: int | None) -> list[dict]:
# #     issues: list[dict] = []

# #     # 1. Repeated words
# #     for match in _REPEATED_WORD_RE.finditer(text):
# #         word = match.group(1).lower()
# #         if word in _REPEATED_WORD_ALLOWLIST:
# #             continue
# #         issues.append(_build_issue(
# #             id         = "grammar-heuristic-repeated-word",
# #             severity   = "warning",
# #             page       = page,
# #             snippet    = match.group(0),            # e.g. "the the"
# #             message    = f"Repeated word detected: '{word} {word}'.",
# #             suggestion = f"Remove one occurrence of '{word}'.",
# #         ))

# #     # 2. Long sentences
# #     for sentence in re.split(r'(?<=[.?!])\s+', text):
# #         words = sentence.split()
# #         if len(words) > 45:
# #             # Show first 100 chars of the sentence as the locator snippet
# #             issues.append(_build_issue(
# #                 id         = "grammar-heuristic-long-sentence",
# #                 severity   = "info",
# #                 page       = page,
# #                 snippet    = sentence[:100],
# #                 message    = f"Sentence is {len(words)} words long (recommended max: 45).",
# #                 suggestion = "Break into two or more shorter sentences for clarity.",
# #             ))

# #     # 3. Contractions
# #     seen_contractions: set[str] = set()
# #     for match in _CONTRACTION_RE.finditer(text):
# #         form = match.group(0).lower()
# #         if form in seen_contractions:
# #             continue
# #         seen_contractions.add(form)
# #         expansion = _CONTRACTION_EXPANSIONS.get(form, "full form")
# #         issues.append(_build_issue(
# #             id         = "grammar-heuristic-contraction",
# #             severity   = "warning",
# #             page       = page,
# #             snippet    = match.group(0),            # e.g. "can't"
# #             message    = f"Informal contraction '{match.group(0)}' is inappropriate in academic writing.",
# #             suggestion = f"Expand to '{expansion}'.",
# #         ))

# #     # 4. First-person pronouns
# #     seen_fp: set[str] = set()
# #     for match in _FIRST_PERSON_RE.finditer(text):
# #         token = match.group(0).lower()
# #         if token in seen_fp:
# #             continue
# #         seen_fp.add(token)
# #         issues.append(_build_issue(
# #             id         = "grammar-heuristic-first-person",
# #             severity   = "warning",
# #             page       = page,
# #             snippet    = match.group(0),            # e.g. "We"
# #             message    = f"First-person pronoun '{match.group(0)}' found.",
# #             suggestion = (
# #                 "Use passive voice or third-person constructions "
# #                 "(e.g. 'The experiment was conducted...' instead of 'We conducted...')."
# #             ),
# #         ))

# #     return issues


# # # ===========================================================================
# # # Layer 2 – LanguageTool
# # # ===========================================================================

# # def _languagetool_checks(text: str, page: int | None) -> list[dict]:
# #     tool = _get_tool()
# #     if tool is None:
# #         return []

# #     try:
# #         matches = tool.check(text)
# #     except Exception as exc:
# #         logger.warning("grammar_checker: LanguageTool.check() failed: %s", exc)
# #         return []

# #     issues: list[dict] = []
# #     for match in matches:
# #         if len(issues) >= _LT_MAX_ISSUES:
# #             break

# #         rule_id = getattr(match, "ruleId", "") or "general"
# #         if rule_id in NOISY_LT_RULE_IDS:
# #             continue

# #         issue_type = getattr(match, "ruleIssueType", "") or ""
# #         severity   = "critical" if issue_type == "misspelling" else "warning"

# #         replacements = getattr(match, "replacements", []) or []
# #         suggestion   = (
# #             f"Try: {', '.join(replacements[:2])}"
# #             if replacements
# #             else "Review sentence structure."
# #         )

# #         # Extract the exact flagged token from LT's context + offset
# #         context  = getattr(match, "context", "") or ""
# #         offset   = getattr(match, "offsetInContext", 0) or 0
# #         length   = getattr(match, "errorLength", 1) or 1
# #         snippet  = context[offset: offset + length].strip() if context else None

# #         issues.append(_build_issue(
# #             id         = f"grammar-lt-{rule_id.lower()}",
# #             severity   = severity,
# #             page       = page,
# #             snippet    = snippet,                   # e.g. "recieve"
# #             message    = getattr(match, "message", "LanguageTool flagged an issue."),
# #             suggestion = suggestion,
# #         ))

# #     return issues


# # # ===========================================================================
# # # Layer 3 – Academic style checks
# # # ===========================================================================

# # def _academic_style_checks(text: str, page: int | None) -> list[dict]:
# #     issues: list[dict] = []

# #     # 1. Subjective first-person phrases
# #     seen_sfp: set[str] = set()
# #     for match in _SUBJECTIVE_FP_RE.finditer(text):
# #         token = match.group(0).lower()
# #         if token in seen_sfp:
# #             continue
# #         seen_sfp.add(token)
# #         issues.append(_build_issue(
# #             id         = "grammar-style-subjective-first-person",
# #             severity   = "warning",
# #             page       = page,
# #             snippet    = match.group(0),            # e.g. "I believe"
# #             message    = f"Subjective first-person phrasing: '{match.group(0)}'.",
# #             suggestion = "Rewrite objectively (e.g. 'The results indicate...').",
# #         ))

# #     # 2. Overconfident claims
# #     seen_oc: set[str] = set()
# #     for match in _OVERCONFIDENT_RE.finditer(text):
# #         token = match.group(0).lower()
# #         if token in seen_oc:
# #             continue
# #         seen_oc.add(token)
# #         issues.append(_build_issue(
# #             id         = "grammar-academic-overconfident-claim",
# #             severity   = "critical",
# #             page       = page,
# #             snippet    = match.group(0),            # e.g. "clearly shows"
# #             message    = (
# #                 f"Overconfident language: '{match.group(0)}'. "
# #                 "Academic claims must be appropriately qualified."
# #             ),
# #             suggestion = (
# #                 "Replace with hedged language such as 'suggests', 'indicates', "
# #                 "'appears to', or 'may demonstrate'."
# #             ),
# #         ))

# #     # 3. Unsupported superlatives
# #     seen_sup: set[str] = set()
# #     for match in _SUPERLATIVE_RE.finditer(text):
# #         token = match.group(0).lower().strip()
# #         if token in seen_sup:
# #             continue
# #         seen_sup.add(token)
# #         issues.append(_build_issue(
# #             id         = "grammar-academic-unsupported-superlative",
# #             severity   = "warning",
# #             page       = page,
# #             snippet    = match.group(0).strip(),    # e.g. "the best"
# #             message    = (
# #                 f"Superlative or absolute claim: '{match.group(0).strip()}'. "
# #                 "This requires explicit comparative evidence or a citation."
# #             ),
# #             suggestion = (
# #                 "Either cite evidence for the claim or use a relative comparative "
# #                 "(e.g. 'outperforms the baseline' instead of 'the best')."
# #             ),
# #         ))

# #     # 4. Vague quantifiers
# #     seen_vq: set[str] = set()
# #     for match in _VAGUE_QUANTIFIER_RE.finditer(text):
# #         token = match.group(0).lower()
# #         if token in seen_vq:
# #             continue
# #         seen_vq.add(token)
# #         issues.append(_build_issue(
# #             id         = "grammar-academic-vague-quantifier",
# #             severity   = "info",
# #             page       = page,
# #             snippet    = match.group(0),            # e.g. "many"
# #             message    = f"Vague quantifier '{match.group(0)}' lacks precision.",
# #             suggestion = (
# #                 "Replace with a specific number or percentage where possible "
# #                 "(e.g. '47 participants' instead of 'many participants')."
# #             ),
# #         ))

# #     # 5. Missing hedging
# #     for match in _MISSING_HEDGE_RE.finditer(text):
# #         start  = max(0, match.start() - 60)
# #         end    = min(len(text), match.end() + 60)
# #         window = text[start:end]
# #         if not _HEDGE_WORDS_RE.search(window):
# #             issues.append(_build_issue(
# #                 id         = "grammar-academic-missing-hedge",
# #                 severity   = "warning",
# #                 page       = page,
# #                 snippet    = match.group(0),        # e.g. "this method performs"
# #                 message    = (
# #                     f"Unhedged claim: '{match.group(0)}'. "
# #                     "Direct assertions without qualification are discouraged."
# #                 ),
# #                 suggestion = (
# #                     "Add hedging language, e.g. 'This method appears to...' "
# #                     "or 'The proposed approach may...'."
# #                 ),
# #             ))

# #     # 6. Active voice in methods / results context
# #     seen_av: set[str] = set()
# #     for match in _ACTIVE_PASSIVE_RE.finditer(text):
# #         phrase = match.group(0).lower()
# #         if phrase in seen_av:
# #             continue
# #         sent_start = text.rfind('.', 0, match.start()) + 1
# #         sent_end   = text.find('.', match.end())
# #         if sent_end == -1:
# #             sent_end = len(text)
# #         sentence = text[sent_start:sent_end]
# #         if _METHOD_RESULT_KWS_RE.search(sentence):
# #             seen_av.add(phrase)
# #             issues.append(_build_issue(
# #                 id         = "grammar-academic-active-voice-methods",
# #                 severity   = "info",
# #                 page       = page,
# #                 snippet    = match.group(0),        # e.g. "we found"
# #                 message    = (
# #                     f"Active voice ('{match.group(0)}') in a methods/results context. "
# #                     "Many venues prefer passive construction here."
# #                 ),
# #                 suggestion = (
# #                     "Consider passive voice, e.g. "
# #                     "'Experiments were conducted...' instead of 'We conducted...'."
# #                 ),
# #             ))

# #     return issues


# # # ===========================================================================
# # # Data Assembler (Bridge from pdf_ingestion)
# # # ===========================================================================

# # def assemble_doc_from_spans(spans: list[dict]) -> dict:
# #     """
# #     BRIDGE FUNCTION:
# #     Converts the 'List of Spans' from pdf_ingestion.py into the
# #     'Page-based Dict' required by check_grammar().
# #     """
# #     pages_map: dict[int, list[str]] = {}

# #     for span in spans:
# #         p_num = span.get("page", 1)
# #         text  = span.get("text", "")
# #         if p_num not in pages_map:
# #             pages_map[p_num] = []
# #         pages_map[p_num].append(text)

# #     return {
# #         "pages": [
# #             {"page_number": p_num, "text": " ".join(pages_map[p_num])}
# #             for p_num in sorted(pages_map.keys())
# #         ]
# #     }


# # # ===========================================================================
# # # Public API
# # # ===========================================================================

# # def check_grammar(parsed_data: dict | list) -> list[dict]:
# #     """
# #     Main entry point -- called by app.py / the central orchestrator.

# #     Parameters
# #     ----------
# #     parsed_data : dict | list
# #         If passed a dict, assumes it is already formatted into pages.
# #         If passed a list, assumes it is the raw 'span' output from
# #         pdf_ingestion.py and automatically assembles it via
# #         assemble_doc_from_spans().

# #     Returns
# #     -------
# #     list[dict]
# #         Aggregated issue list across all pages.
# #         Every issue contains: id, category, severity, page, snippet,
# #         message, suggestion.
# #     """
# #     all_issues: list[dict] = []

# #     # Auto-detect input format
# #     if isinstance(parsed_data, list):
# #         parsed_doc = assemble_doc_from_spans(parsed_data)
# #         logger.info(
# #             "Auto-assembled %d spans into %d pages.",
# #             len(parsed_data), len(parsed_doc.get("pages", []))
# #         )
# #     else:
# #         parsed_doc = parsed_data

# #     if not parsed_doc or "pages" not in parsed_doc:
# #         logger.warning("grammar_checker.check_grammar: empty or malformed parsed_doc.")
# #         return all_issues

# #     for page_data in parsed_doc.get("pages", []):
# #         page_num = page_data.get("page_number")
# #         raw_text = page_data.get("text", "") or ""

# #         if not raw_text.strip():
# #             continue

# #         clean_text = _normalize_for_grammar(raw_text)

# #         # --- Layer 1 ---
# #         try:
# #             layer1 = _heuristic_checks(clean_text, page_num)
# #             logger.debug("Page %s | Layer 1: %d issues.", page_num, len(layer1))
# #             all_issues.extend(layer1)
# #         except Exception as exc:
# #             logger.error("Page %s | Layer 1 crashed: %s", page_num, exc, exc_info=True)

# #         # --- Layer 2 ---
# #         try:
# #             layer2 = _languagetool_checks(clean_text, page_num)
# #             logger.debug("Page %s | Layer 2: %d issues.", page_num, len(layer2))
# #             all_issues.extend(layer2)
# #         except Exception as exc:
# #             logger.error("Page %s | Layer 2 crashed: %s", page_num, exc, exc_info=True)

# #         # --- Layer 3 ---
# #         try:
# #             layer3 = _academic_style_checks(clean_text, page_num)
# #             logger.debug("Page %s | Layer 3: %d issues.", page_num, len(layer3))
# #             all_issues.extend(layer3)
# #         except Exception as exc:
# #             logger.error("Page %s | Layer 3 crashed: %s", page_num, exc, exc_info=True)

# #     logger.info("grammar_checker: %d total issues across all pages.", len(all_issues))
# #     return all_issues

# """
# modules/grammar_checker.py
# ==========================
# 3-layer grammar & academic-style checker for the AI-Powered Research Paper Checker.

# Public API
# ----------
#     check_grammar(parsed_data: dict | list) -> list[dict]
#     assemble_doc_from_spans(spans: list[dict]) -> dict

# Layers
# ------
#     Layer 1  –  Heuristics     (pure Python / regex, zero external deps)
#     Layer 2  –  LanguageTool   (Java NLP, singleton, retry-once, graceful degradation)
#     Layer 3  –  Academic style (original contribution)

# Issue schema — every issue returned has exactly these keys
# ----------------------------------------------------------
#     {
#         "id":         str,
#         "category":   "grammar",
#         "severity":   "critical" | "warning" | "info",
#         "page":       int | None,
#         "snippet":    str | None,
#         "message":    str,
#         "suggestion": str,
#     }

# Architecture notes
# ------------------
# - check_grammar() iterates parsed_doc page-by-page so every issue carries an
#   accurate page number from the source.
# - Singleton pattern: LanguageTool JVM started once, retry-once on failure.
# - _normalize_for_grammar() strips equations, references, math, citations, and
#   PDF line-break hyphens before any layer sees the text.
# - NOISY_LT_RULE_IDS suppresses rules that fire constantly on technical text.
# - LanguageTool output capped at _LT_MAX_ISSUES (12) per page.

# Key fix (v2)
# ------------
# - Normalizer now strips PDF line-break hyphens (e.g. "pro-\ncedure" → "procedure")
# - Normalizer strips isolated single-letter tokens that are math variables
# - _REPEATED_WORD_RE allowlist extended to cover single-character math vars
# - Long-sentence check now skips sentences that contain equation residue
#   (digit-heavy or symbol-heavy strings that PyMuPDF extracts from equations)
# - First-person check now skips standalone 'I' that appears next to digits or
#   math symbols (i.e. it is a variable, not a pronoun)
# - LanguageTool NOISY blocklist extended with rules that fire on technical text
# """

# from __future__ import annotations

# import logging
# import re
# from typing import Any

# logger = logging.getLogger(__name__)

# # ---------------------------------------------------------------------------
# # Constants
# # ---------------------------------------------------------------------------

# NOISY_LT_RULE_IDS: set[str] = {
#     "WHITESPACE_RULE",
#     "DOUBLE_PUNCTUATION",
#     "COMMA_PARENTHESIS_WHITESPACE",
#     "EN_QUOTES",
#     "DASH_RULE",
#     "UPPERCASE_SENTENCE_START",
#     "PUNCTUATION_PARAGRAPH_END",
#     "SENTENCE_WHITESPACE",
#     "MORFOLOGIK_RULE_EN_US",          # noisy on acronyms / variable names
#     "EN_UNPAIRED_BRACKETS",
#     "ARROWS",
#     "UNLIKELY_OPENING_PUNCTUATION",
#     "REPEATED_WORDS_3X",
#     # Additional rules that fire heavily on equation-rich technical papers
#     "WORD_CONTAINS_UNDERSCORE",
#     "UNPAIRED_BRACKETS",
#     "PUNCTUATION_SPACE",
#     "COMMA_COMPOUND_SENTENCE",
#     "AGREEMENT_SENT",
#     "EN_A_VS_AN",
#     "NEEDLESS_VARIANT",
#     "HYPHENATED_WORDS_COMPOUNDS",
#     "UNNECESSARY_HYPHEN",
# }

# # ---------------------------------------------------------------------------
# # Normalizer compiled patterns
# # ---------------------------------------------------------------------------
# _REF_SECTION_RE   = re.compile(r'\b(references|bibliography)\b.*',
#                                 re.IGNORECASE | re.DOTALL)
# _DOI_RE           = re.compile(r'\bdoi:\s*\S+', re.IGNORECASE)
# _URL_RE           = re.compile(r'https?://\S+')
# _EQUATION_RE      = re.compile(r'\$[^$]+\$|\\\([^)]+\\\)|\\\[[^\]]+\\\]')
# _CITATION_TAG_RE  = re.compile(r'\[[\d,\-\s]+\]|\([A-Za-z\s]+,\s\d{4}\)')
# _TABLE_CAPTION_RE = re.compile(r'\b(table|figure|fig\.?)\s+\d+', re.IGNORECASE)
# _MATH_TOKENS_RE   = re.compile(r'[=<>≤≥±×÷∑∫∂√∞α-ωΑ-Ω·°]')

# # PDF line-break hyphens: "pro-\ncedure" or "pro- cedure" → "procedure"
# # PyMuPDF preserves these as literal hyphen + newline/space
# _LINEBREAK_HYPHEN_RE = re.compile(r'(\w)-\n(\w)')
# _LINEBREAK_HYPHEN_SPACE_RE = re.compile(r'(\w)- ([a-z])')

# # Equation residue: lines that are mostly digits, operators, variable tokens
# # These come from PyMuPDF extracting typeset math as plain text
# # A "sentence" is equation residue if it has a very high ratio of non-alpha chars
# def _is_equation_residue(text: str) -> bool:
#     """Return True if this text looks like extracted equation content, not prose."""
#     if len(text) < 5:
#         return True
#     alpha = sum(1 for c in text if c.isalpha())
#     ratio = alpha / len(text)
#     # Less than 40% alphabetic = mostly numbers/symbols = equation
#     if ratio < 0.40:
#         return True
#     # Single-character tokens repeated (e.g. "n n", "x x", "k k")
#     if re.match(r'^[a-zA-Z]\s+[a-zA-Z]$', text.strip()):
#         return True
#     return False

# # ---------------------------------------------------------------------------
# # Layer 1 – heuristic patterns
# # ---------------------------------------------------------------------------
# _REPEATED_WORD_RE = re.compile(r'\b(\w+)\s+\1\b', re.IGNORECASE)

# # Allowlist for valid double-word constructions AND single math variable chars
# # Single letters as words are almost always math variables in technical papers
# _REPEATED_WORD_ALLOWLIST: set[str] = {
#     "had", "that",
#     # Single-letter math variables that appear doubled in equations
#     "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
#     "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
# }

# _CONTRACTION_RE = re.compile(
#     r"\b(can't|won't|don't|doesn't|didn't|isn't|aren't|wasn't|weren't|"
#     r"it's|i'm|i've|i'd|i'll|we're|we've|we'd|we'll|you're|they're|"
#     r"he's|she's|that's|there's|here's|let's|who's|what's)\b",
#     re.IGNORECASE,
# )
# _CONTRACTION_EXPANSIONS: dict[str, str] = {
#     "can't":   "cannot",
#     "won't":   "will not",
#     "don't":   "do not",
#     "doesn't": "does not",
#     "didn't":  "did not",
#     "isn't":   "is not",
#     "aren't":  "are not",
#     "wasn't":  "was not",
#     "weren't": "were not",
#     "it's":    "it is / its",
#     "i'm":     "I am",
#     "i've":    "I have",
#     "i'd":     "I would / I had",
#     "i'll":    "I will",
#     "we're":   "we are",
#     "we've":   "we have",
#     "we'd":    "we would / we had",
#     "we'll":   "we will",
#     "you're":  "you are",
#     "they're": "they are",
#     "he's":    "he is / he has",
#     "she's":   "she is / she has",
#     "that's":  "that is / that has",
#     "there's": "there is / there has",
#     "here's":  "here is",
#     "let's":   "let us",
#     "who's":   "who is / who has",
#     "what's":  "what is / what has",
# }

# # First-person: match 'I' only when it is a standalone word surrounded by
# # normal prose characters, NOT when adjacent to digits or math punctuation.
# # This filters "variable I" (e.g. "J = I × r") from "pronoun I" ("I believe").
# _FIRST_PERSON_RE = re.compile(r'\b(I|me|my|myself|we|our|ours|ourselves)\b')
# # Context pattern: if 'I' is surrounded by digits/math it's a variable
# _MATH_CONTEXT_RE = re.compile(r'[\d\+\-\*/\^=,\(\)\[\]\.]\s*I\s*[\d\+\-\*/\^=,\(\)\[\]\.]')

# # ---------------------------------------------------------------------------
# # Layer 3 – academic style patterns
# # ---------------------------------------------------------------------------
# _SUBJECTIVE_FP_RE = re.compile(
#     r'\b(I believe|In my opinion|As I have shown|I think|I feel|'
#     r'In my view|I argue that|I claim that)\b',
#     re.IGNORECASE,
# )
# _OVERCONFIDENT_RE = re.compile(
#     r'\b(proves?|guarantees?|demonstrates? conclusively|shows? definitively|'
#     r'undeniably|certainly|it is clear that|clearly shows?|obviously|'
#     r'without (any )?doubt|it is evident that|unquestionably)\b',
#     re.IGNORECASE,
# )
# _SUPERLATIVE_RE = re.compile(
#     r'\b(the\s+)?(best|worst|fastest|slowest|most\s+accurate|most\s+efficient|'
#     r'most\s+effective|most\s+advanced|state-of-the-art|unprecedented|'
#     r'superior to all|outperforms? all|novel(?!\w))\b',
#     re.IGNORECASE,
# )
# _VAGUE_QUANTIFIER_RE = re.compile(
#     r'\b(many|few|several|some|a number of|various|numerous|a lot of|'
#     r'most|majority of|large amount of|small amount of)\b',
#     re.IGNORECASE,
# )
# _MISSING_HEDGE_RE = re.compile(
#     r'\b(this\s+(model|method|approach|system|algorithm|framework|technique)'
#     r'\s+(is|works|performs|achieves|provides|yields|produces|improves))\b',
#     re.IGNORECASE,
# )
# _HEDGE_WORDS_RE = re.compile(
#     r'\b(suggests?|indicates?|appears?\s+to|seems?\s+to|may|might|could|'
#     r'is likely|tends?\s+to|is expected to)\b',
#     re.IGNORECASE,
# )
# _ACTIVE_PASSIVE_RE = re.compile(
#     r'\b(we\s+(found|observed|note|conclude|believe|claim|argue|show|propose|'
#     r'present|demonstrate|evaluate|compare|analyse|analyze))\b',
#     re.IGNORECASE,
# )
# _METHOD_RESULT_KWS_RE = re.compile(
#     r'\b(experiment|evaluation|dataset|baseline|results?|training|testing|'
#     r'validation|accuracy|performance|benchmark)\b',
#     re.IGNORECASE,
# )

# _LT_MAX_ISSUES = 12

# # ---------------------------------------------------------------------------
# # Module-level singleton state
# # ---------------------------------------------------------------------------
# _lt_tool: Any | None = None
# _lt_failed: bool = False


# # ===========================================================================
# # Private helpers
# # ===========================================================================

# def _build_issue(
#     *,
#     id: str,
#     severity: str,
#     page: int | None,
#     snippet: str | None,
#     message: str,
#     suggestion: str,
# ) -> dict:
#     """Single source of truth for the issue schema."""
#     if snippet:
#         snippet = snippet.strip()[:120]
#     return {
#         "id":         id,
#         "category":   "grammar",
#         "severity":   severity,
#         "page":       page,
#         "snippet":    snippet,
#         "message":    message,
#         "suggestion": suggestion,
#     }


# def _get_tool():
#     """Return the LanguageTool singleton (retry-once on failure)."""
#     global _lt_tool, _lt_failed

#     if _lt_failed:
#         return None
#     if _lt_tool is not None:
#         return _lt_tool

#     import time

#     for attempt in (1, 2):
#         try:
#             import language_tool_python    # noqa: PLC0415
#             logger.info("[INFO] Starting LanguageTool Java Server (attempt %d/2)...", attempt)
#             _lt_tool = language_tool_python.LanguageTool("en-US")
#             logger.info("[INFO] LanguageTool ready.")
#             return _lt_tool
#         except Exception as exc:           # noqa: BLE001
#             logger.warning("[ERROR] LanguageTool attempt %d/2 failed: %s", attempt, exc)
#             if attempt == 1:
#                 time.sleep(2)

#     _lt_failed = True
#     logger.warning(
#         "[ERROR] LanguageTool unavailable after 2 attempts -- "
#         "Layer 2 will be skipped for the remainder of this session."
#     )
#     return None


# def _find_page_for_snippet(snippet: str, parsed_doc: dict) -> int | None:
#     """Fallback page locator."""
#     if not snippet or not isinstance(parsed_doc, dict):
#         return None
#     snippet_lower = snippet.lower().strip()
#     for page in parsed_doc.get("pages", []):
#         if snippet_lower in (page.get("text") or "").lower():
#             return page.get("page_number")
#     return None


# def _is_reference_section_start(text: str) -> bool:
#     """
#     NEW: Detect if this page contains a References/Bibliography section HEADING.
    
#     Looks for standalone section headers (first few lines) like:
#       - "References"
#       - "References:"
#       - "REFERENCES"
#       - "Bibliography"
#       - "Works Cited"
    
#     Only checks first 3 lines to avoid false positives from mentions in prose.
#     Ignores mentions like "see References section" in the middle of text.
#     """
#     if not text or not text.strip():
#         return False
    
#     lines = text.strip().split('\n')
#     ref_keywords = {"references", "bibliography", "works cited", "citations", "cited works"}
    
#     # Check only first 3 lines of the page (likely where a section heading appears)
#     for i, line in enumerate(lines[:3]):
#         stripped = line.strip().lower()
        
#         # Skip very short residue or empty lines
#         if not stripped or len(stripped) > 50:
#             continue
        
#         # Match standalone keyword (with optional colon or number suffix for numbering)
#         for keyword in ref_keywords:
#             # Patterns:
#             # "References" or "References:" or "References 1" or similar
#             if re.match(rf'^\s*{keyword}\s*(:|$|[0-9])', stripped, re.IGNORECASE):
#                 logger.debug(f"Detected reference section heading on line {i}: '{line.strip()}'")
#                 return True
    
#     return False


# def _is_likely_acronym_or_name(snippet: str) -> bool:
#     """
#     NEW: Filter snippets that are likely acronyms, proper nouns, or technical terms.
#     Don't flag these as spelling errors since they're domain-specific.
#     """
#     if not snippet or len(snippet) < 2:
#         return False
    
#     # All uppercase (acronyms): CNN, BERT, IEEE, LSTM, etc.
#     if snippet.isupper() and len(snippet) >= 2:
#         return True
    
#     # Contains digits (likely variable/model names): BERT2, ResNet50, etc.
#     if any(c.isdigit() for c in snippet):
#         return True
    
#     # Contains underscores (likely variable/method names: my_var, __init__)
#     if '_' in snippet:
#         return True
    
#     # Title case + short (likely proper noun: Smith, John, etc.)
#     if snippet and snippet[0].isupper() and len(snippet) <= 15:
#         # In citation context, single words capitalized are often names
#         return True
    
#     return False


# # COMMENTED OUT (old version):
# # def _normalize_for_grammar(text: str) -> str:
# #     """
# #     Strip non-prose content before any layer sees the text.
# #
# #     Order matters:
# #     1. Fix PDF line-break hyphens FIRST ("pro-\\ncedure" → "procedure")
# #     2. Strip References section
# #     3. Strip DOIs, URLs
# #     4. Strip LaTeX equations
# #     5. Strip citation tags
# #     6. Strip table/figure labels
# #     7. Strip math operator characters
# #     8. Collapse whitespace
# #     """
# #     # 1. Fix PDF line-break hyphens (PyMuPDF preserves "pro-\ncedure")
# #     text = _LINEBREAK_HYPHEN_RE.sub(r'\1\2', text)
# #     text = _LINEBREAK_HYPHEN_SPACE_RE.sub(r'\1\2', text)
# #
# #     # 2-7. Standard normalisation
# #     text = _REF_SECTION_RE.sub(" ", text)
# #     text = _DOI_RE.sub(" ", text)
# #     text = _URL_RE.sub(" ", text)
# #     text = _EQUATION_RE.sub(" ", text)
# #     text = _CITATION_TAG_RE.sub(" ", text)
# #     text = _TABLE_CAPTION_RE.sub(" ", text)
# #     text = _MATH_TOKENS_RE.sub(" ", text)
# #
# #     # 8. Collapse whitespace
# #     text = re.sub(r'[ \t]{2,}', ' ', text)
# #     return text.strip()


# # NEW version (same logic, kept for now):
# def _normalize_for_grammar(text: str) -> str:
#     """
#     Strip non-prose content before any layer sees the text.

#     Order matters:
#     1. Fix PDF line-break hyphens FIRST ("pro-\\ncedure" → "procedure")
#     2. Strip References section
#     3. Strip DOIs, URLs
#     4. Strip LaTeX equations
#     5. Strip citation tags
#     6. Strip table/figure labels
#     7. Strip math operator characters
#     8. Collapse whitespace
#     """
#     # 1. Fix PDF line-break hyphens (PyMuPDF preserves "pro-\ncedure")
#     text = _LINEBREAK_HYPHEN_RE.sub(r'\1\2', text)
#     text = _LINEBREAK_HYPHEN_SPACE_RE.sub(r'\1\2', text)

#     # 2-7. Standard normalisation
#     text = _REF_SECTION_RE.sub(" ", text)
#     text = _DOI_RE.sub(" ", text)
#     text = _URL_RE.sub(" ", text)
#     text = _EQUATION_RE.sub(" ", text)
#     text = _CITATION_TAG_RE.sub(" ", text)
#     text = _TABLE_CAPTION_RE.sub(" ", text)
#     text = _MATH_TOKENS_RE.sub(" ", text)

#     # 8. Collapse whitespace
#     text = re.sub(r'[ \t]{2,}', ' ', text)
#     return text.strip()


# # ===========================================================================
# # Layer 1 – Heuristic checks
# # ===========================================================================

# def _heuristic_checks(text: str, page: int | None) -> list[dict]:
#     issues: list[dict] = []

#     # ------------------------------------------------------------------
#     # 1. Repeated words
#     #    Skip: allowlisted words (valid doubles + single math var letters)
#     # ------------------------------------------------------------------
#     for match in _REPEATED_WORD_RE.finditer(text):
#         word = match.group(1).lower()
#         if word in _REPEATED_WORD_ALLOWLIST:
#             continue
#         issues.append(_build_issue(
#             id         = "grammar-heuristic-repeated-word",
#             severity   = "warning",
#             page       = page,
#             snippet    = match.group(0),
#             message    = f"Repeated word detected: '{word} {word}'.",
#             suggestion = f"Remove one occurrence of '{word}'.",
#         ))

#     # ------------------------------------------------------------------
#     # 2. Long sentences
#     #    Skip sentences that are equation residue (PyMuPDF math extraction)
#     # ------------------------------------------------------------------
#     for sentence in re.split(r'(?<=[.?!])\s+', text):
#         words = sentence.split()
#         if len(words) > 45:
#             # Skip if this "sentence" is actually extracted equation text
#             if _is_equation_residue(sentence):
#                 continue
#             issues.append(_build_issue(
#                 id         = "grammar-heuristic-long-sentence",
#                 severity   = "info",
#                 page       = page,
#                 snippet    = sentence[:100],
#                 message    = f"Sentence is {len(words)} words long (recommended max: 45).",
#                 suggestion = "Break into two or more shorter sentences for clarity.",
#             ))

#     # ------------------------------------------------------------------
#     # 3. Contractions
#     # ------------------------------------------------------------------
#     seen_contractions: set[str] = set()
#     for match in _CONTRACTION_RE.finditer(text):
#         form = match.group(0).lower()
#         if form in seen_contractions:
#             continue
#         seen_contractions.add(form)
#         expansion = _CONTRACTION_EXPANSIONS.get(form, "full form")
#         issues.append(_build_issue(
#             id         = "grammar-heuristic-contraction",
#             severity   = "warning",
#             page       = page,
#             snippet    = match.group(0),
#             message    = f"Informal contraction '{match.group(0)}' is inappropriate in academic writing.",
#             suggestion = f"Expand to '{expansion}'.",
#         ))

#     # ------------------------------------------------------------------
#     # 4. First-person pronouns
#     #    Skip standalone 'I' that is a math variable (adjacent to digits/operators)
#     # ------------------------------------------------------------------
#     seen_fp: set[str] = set()
#     for match in _FIRST_PERSON_RE.finditer(text):
#         token = match.group(0)
#         token_lower = token.lower()

#         # For the pronoun 'I' specifically, check it's not a math variable
#         if token == "I":
#             # Get surrounding context (10 chars each side)
#             start  = max(0, match.start() - 10)
#             end    = min(len(text), match.end() + 10)
#             window = text[start:end]
#             # If surrounded by math context, skip
#             if re.search(r'[\d\+\-\*/\^=,\(\)\[\]\.]', window):
#                 continue

#         if token_lower in seen_fp:
#             continue
#         seen_fp.add(token_lower)
#         issues.append(_build_issue(
#             id         = "grammar-heuristic-first-person",
#             severity   = "warning",
#             page       = page,
#             snippet    = token,
#             message    = f"First-person pronoun '{token}' found.",
#             suggestion = (
#                 "Use passive voice or third-person constructions "
#                 "(e.g. 'The experiment was conducted...' instead of 'We conducted...')."
#             ),
#         ))

#     return issues


# # ===========================================================================
# # Layer 2 – LanguageTool
# # ===========================================================================

# # COMMENTED OUT (old version without acronym/name filtering):
# # def _languagetool_checks(text: str, page: int | None) -> list[dict]:
# #     tool = _get_tool()
# #     if tool is None:
# #         return []
# #
# #     try:
# #         matches = tool.check(text)
# #     except Exception as exc:
# #         logger.warning("grammar_checker: LanguageTool.check() failed: %s", exc)
# #         return []
# #
# #     issues: list[dict] = []
# #     for match in matches:
# #         if len(issues) >= _LT_MAX_ISSUES:
# #             break
# #
# #         rule_id = getattr(match, "ruleId", "") or "general"
# #         if rule_id in NOISY_LT_RULE_IDS:
# #             continue
# #
# #         issue_type = getattr(match, "ruleIssueType", "") or ""
# #         severity   = "critical" if issue_type == "misspelling" else "warning"
# #
# #         replacements = getattr(match, "replacements", []) or []
# #         suggestion   = (
# #             f"Try: {', '.join(replacements[:2])}"
# #             if replacements
# #             else "Review sentence structure."
# #         )
# #
# #         context  = getattr(match, "context", "") or ""
# #         offset   = getattr(match, "offsetInContext", 0) or 0
# #         length   = getattr(match, "errorLength", 1) or 1
# #         snippet  = context[offset: offset + length].strip() if context else None
# #
# #         # Skip if snippet looks like a math variable (single letter or digit string)
# #         if snippet and re.match(r'^[a-zA-Z\d]{1,3}$', snippet):
# #             continue
# #
# #         # Fix: if snippet is just punctuation, use broader context
# #         if not snippet or snippet in {".", ",", "!", "?", "(", ")"}:
# #             snippet = context.strip()[:80] if context else None
# #
# #         issues.append(_build_issue(
# #             id         = f"grammar-lt-{rule_id.lower()}",
# #             severity   = severity,
# #             page       = page,
# #             snippet    = snippet,
# #             message    = getattr(match, "message", "LanguageTool flagged an issue."),
# #             suggestion = suggestion,
# #         ))
# #
# #     return issues


# # NEW version with acronym/name filtering:
# def _languagetool_checks(text: str, page: int | None) -> list[dict]:
#     """LanguageTool checks with NEW: filtering of acronyms and names."""
#     tool = _get_tool()
#     if tool is None:
#         return []

#     try:
#         matches = tool.check(text)
#     except Exception as exc:
#         logger.warning("grammar_checker: LanguageTool.check() failed: %s", exc)
#         return []

#     issues: list[dict] = []
#     for match in matches:
#         if len(issues) >= _LT_MAX_ISSUES:
#             break

#         rule_id = getattr(match, "ruleId", "") or "general"
#         if rule_id in NOISY_LT_RULE_IDS:
#             continue

#         issue_type = getattr(match, "ruleIssueType", "") or ""
#         severity   = "critical" if issue_type == "misspelling" else "warning"

#         replacements = getattr(match, "replacements", []) or []
#         suggestion   = (
#             f"Try: {', '.join(replacements[:2])}"
#             if replacements
#             else "Review sentence structure."
#         )

#         context  = getattr(match, "context", "") or ""
#         offset   = getattr(match, "offsetInContext", 0) or 0
#         length   = getattr(match, "errorLength", 1) or 1
#         snippet  = context[offset: offset + length].strip() if context else None

#         # Skip if snippet looks like a math variable (single letter or digit string)
#         if snippet and re.match(r'^[a-zA-Z\d]{1,3}$', snippet):
#             continue

#         # NEW: Skip if snippet is likely an acronym, technical term, or proper name
#         if snippet and _is_likely_acronym_or_name(snippet):
#             logger.debug(f"Skipping likely acronym/name: {snippet}")
#             continue

#         # Fix: if snippet is just punctuation, use broader context
#         if not snippet or snippet in {".", ",", "!", "?", "(", ")"}:
#             snippet = context.strip()[:80] if context else None

#         issues.append(_build_issue(
#             id         = f"grammar-lt-{rule_id.lower()}",
#             severity   = severity,
#             page       = page,
#             snippet    = snippet,
#             message    = getattr(match, "message", "LanguageTool flagged an issue."),
#             suggestion = suggestion,
#         ))

#     return issues


# # ===========================================================================
# # Layer 3 – Academic style checks
# # ===========================================================================

# def _academic_style_checks(text: str, page: int | None) -> list[dict]:
#     issues: list[dict] = []

#     # 1. Subjective first-person phrases
#     seen_sfp: set[str] = set()
#     for match in _SUBJECTIVE_FP_RE.finditer(text):
#         token = match.group(0).lower()
#         if token in seen_sfp:
#             continue
#         seen_sfp.add(token)
#         issues.append(_build_issue(
#             id         = "grammar-style-subjective-first-person",
#             severity   = "warning",
#             page       = page,
#             snippet    = match.group(0),
#             message    = f"Subjective first-person phrasing: '{match.group(0)}'.",
#             suggestion = "Rewrite objectively (e.g. 'The results indicate...').",
#         ))

#     # 2. Overconfident claims
#     seen_oc: set[str] = set()
#     for match in _OVERCONFIDENT_RE.finditer(text):
#         token = match.group(0).lower()
#         if token in seen_oc:
#             continue
#         seen_oc.add(token)
#         issues.append(_build_issue(
#             id         = "grammar-academic-overconfident-claim",
#             severity   = "critical",
#             page       = page,
#             snippet    = match.group(0),
#             message    = (
#                 f"Overconfident language: '{match.group(0)}'. "
#                 "Academic claims must be appropriately qualified."
#             ),
#             suggestion = (
#                 "Replace with hedged language such as 'suggests', 'indicates', "
#                 "'appears to', or 'may demonstrate'."
#             ),
#         ))

#     # 3. Unsupported superlatives
#     seen_sup: set[str] = set()
#     for match in _SUPERLATIVE_RE.finditer(text):
#         token = match.group(0).lower().strip()
#         if token in seen_sup:
#             continue
#         seen_sup.add(token)
#         issues.append(_build_issue(
#             id         = "grammar-academic-unsupported-superlative",
#             severity   = "warning",
#             page       = page,
#             snippet    = match.group(0).strip(),
#             message    = (
#                 f"Superlative or absolute claim: '{match.group(0).strip()}'. "
#                 "This requires explicit comparative evidence or a citation."
#             ),
#             suggestion = (
#                 "Either cite evidence for the claim or use a relative comparative "
#                 "(e.g. 'outperforms the baseline' instead of 'the best')."
#             ),
#         ))

#     # 4. Vague quantifiers
#     seen_vq: set[str] = set()
#     for match in _VAGUE_QUANTIFIER_RE.finditer(text):
#         token = match.group(0).lower()
#         if token in seen_vq:
#             continue
#         seen_vq.add(token)
#         issues.append(_build_issue(
#             id         = "grammar-academic-vague-quantifier",
#             severity   = "info",
#             page       = page,
#             snippet    = match.group(0),
#             message    = f"Vague quantifier '{match.group(0)}' lacks precision.",
#             suggestion = (
#                 "Replace with a specific number or percentage where possible "
#                 "(e.g. '47 participants' instead of 'many participants')."
#             ),
#         ))

#     # 5. Missing hedging
#     for match in _MISSING_HEDGE_RE.finditer(text):
#         start  = max(0, match.start() - 60)
#         end    = min(len(text), match.end() + 60)
#         window = text[start:end]
#         if not _HEDGE_WORDS_RE.search(window):
#             issues.append(_build_issue(
#                 id         = "grammar-academic-missing-hedge",
#                 severity   = "warning",
#                 page       = page,
#                 snippet    = match.group(0),
#                 message    = (
#                     f"Unhedged claim: '{match.group(0)}'. "
#                     "Direct assertions without qualification are discouraged."
#                 ),
#                 suggestion = (
#                     "Add hedging language, e.g. 'This method appears to...' "
#                     "or 'The proposed approach may...'."
#                 ),
#             ))

#     # 6. Active voice in methods / results context
#     seen_av: set[str] = set()
#     for match in _ACTIVE_PASSIVE_RE.finditer(text):
#         phrase = match.group(0).lower()
#         if phrase in seen_av:
#             continue
#         sent_start = text.rfind('.', 0, match.start()) + 1
#         sent_end   = text.find('.', match.end())
#         if sent_end == -1:
#             sent_end = len(text)
#         sentence = text[sent_start:sent_end]
#         if _METHOD_RESULT_KWS_RE.search(sentence):
#             seen_av.add(phrase)
#             issues.append(_build_issue(
#                 id         = "grammar-academic-active-voice-methods",
#                 severity   = "info",
#                 page       = page,
#                 snippet    = match.group(0),
#                 message    = (
#                     f"Active voice ('{match.group(0)}') in a methods/results context. "
#                     "Many venues prefer passive construction here."
#                 ),
#                 suggestion = (
#                     "Consider passive voice, e.g. "
#                     "'Experiments were conducted...' instead of 'We conducted...'."
#                 ),
#             ))

#     return issues


# # ===========================================================================
# # Data Assembler (Bridge from pdf_ingestion)
# # ===========================================================================

# def assemble_doc_from_spans(spans: list[dict]) -> dict:
#     """
#     Convert the flat span list from pdf_ingestion.extract_structure()
#     into the page-grouped dict required by check_grammar().
#     """
#     pages_map: dict[int, list[str]] = {}

#     for span in spans:
#         p_num = span.get("page", 1)
#         text  = span.get("text", "")
#         if p_num not in pages_map:
#             pages_map[p_num] = []
#         pages_map[p_num].append(text)

#     return {
#         "pages": [
#             {"page_number": p_num, "text": " ".join(pages_map[p_num])}
#             for p_num in sorted(pages_map.keys())
#         ]
#     }


# # ===========================================================================
# # Public API
# # ===========================================================================

# # COMMENTED OUT (old version without References section skipping):
# # def check_grammar(parsed_data: dict | list) -> list[dict]:
# #     """
# #     Main entry point -- called by app.py / the central orchestrator.
# #
# #     Parameters
# #     ----------
# #     parsed_data : dict | list
# #         If a list, assumes raw span output from pdf_ingestion and assembles
# #         it automatically. If a dict, assumes already page-grouped format.
# #
# #     Returns
# #     -------
# #     list[dict]
# #         Aggregated issue list across all pages.
# #     """
# #     all_issues: list[dict] = []
# #
# #     if isinstance(parsed_data, list):
# #         parsed_doc = assemble_doc_from_spans(parsed_data)
# #         logger.info(
# #             "Auto-assembled %d spans into %d pages.",
# #             len(parsed_data), len(parsed_doc.get("pages", []))
# #         )
# #     else:
# #         parsed_doc = parsed_data
# #
# #     if not parsed_doc or "pages" not in parsed_doc:
# #         logger.warning("grammar_checker.check_grammar: empty or malformed parsed_doc.")
# #         return all_issues
# #
# #     for page_data in parsed_doc.get("pages", []):
# #         page_num = page_data.get("page_number")
# #         raw_text = page_data.get("text", "") or ""
# #
# #         if not raw_text.strip():
# #             continue
# #
# #         clean_text = _normalize_for_grammar(raw_text)
# #
# #         try:
# #             layer1 = _heuristic_checks(clean_text, page_num)
# #             logger.debug("Page %s | Layer 1: %d issues.", page_num, len(layer1))
# #             all_issues.extend(layer1)
# #         except Exception as exc:
# #             logger.error("Page %s | Layer 1 crashed: %s", page_num, exc, exc_info=True)
# #
# #         try:
# #             layer2 = _languagetool_checks(clean_text, page_num)
# #             logger.debug("Page %s | Layer 2: %d issues.", page_num, len(layer2))
# #             all_issues.extend(layer2)
# #         except Exception as exc:
# #             logger.error("Page %s | Layer 2 crashed: %s", page_num, exc, exc_info=True)
# #
# #         try:
# #             layer3 = _academic_style_checks(clean_text, page_num)
# #             logger.debug("Page %s | Layer 3: %d issues.", page_num, len(layer3))
# #             all_issues.extend(layer3)
# #         except Exception as exc:
# #             logger.error("Page %s | Layer 3 crashed: %s", page_num, exc, exc_info=True)
# #
# #     logger.info("grammar_checker: %d total issues across all pages.", len(all_issues))
# #     return all_issues


# # NEW version with References section detection:
# def check_grammar(parsed_data: dict | list) -> list[dict]:
#     """
#     Main entry point -- called by app.py / the central orchestrator.

#     Parameters
#     ----------
#     parsed_data : dict | list
#         If a list, assumes raw span output from pdf_ingestion and assembles
#         it automatically. If a dict, assumes already page-grouped format.

#     Returns
#     -------
#     list[dict]
#         Aggregated issue list across all pages.
#         NEW: Skips grammar checking from the References section onward.
#     """
#     all_issues: list[dict] = []

#     if isinstance(parsed_data, list):
#         parsed_doc = assemble_doc_from_spans(parsed_data)
#         logger.info(
#             "Auto-assembled %d spans into %d pages.",
#             len(parsed_data), len(parsed_doc.get("pages", []))
#         )
#     else:
#         parsed_doc = parsed_data

#     if not parsed_doc or "pages" not in parsed_doc:
#         logger.warning("grammar_checker.check_grammar: empty or malformed parsed_doc.")
#         return all_issues

#     # NEW: Track if we've entered the References section
#     hit_references = False

#     for page_data in parsed_doc.get("pages", []):
#         page_num = page_data.get("page_number")
#         raw_text = page_data.get("text", "") or ""

#         if not raw_text.strip():
#             continue

#         # NEW: Check if this page starts with or contains a References heading
#         # Once we hit References, skip all further grammar checking
#         if _is_reference_section_start(raw_text):
#             logger.info("Page %s | References section detected. Skipping grammar checks for this and subsequent pages.", page_num)
#             hit_references = True

#         if hit_references:
#             logger.debug("Page %s | Skipped (in References section).", page_num)
#             continue

#         clean_text = _normalize_for_grammar(raw_text)

#         try:
#             layer1 = _heuristic_checks(clean_text, page_num)
#             logger.debug("Page %s | Layer 1: %d issues.", page_num, len(layer1))
#             all_issues.extend(layer1)
#         except Exception as exc:
#             logger.error("Page %s | Layer 1 crashed: %s", page_num, exc, exc_info=True)

#         try:
#             layer2 = _languagetool_checks(clean_text, page_num)
#             logger.debug("Page %s | Layer 2: %d issues.", page_num, len(layer2))
#             all_issues.extend(layer2)
#         except Exception as exc:
#             logger.error("Page %s | Layer 2 crashed: %s", page_num, exc, exc_info=True)

#         try:
#             layer3 = _academic_style_checks(clean_text, page_num)
#             logger.debug("Page %s | Layer 3: %d issues.", page_num, len(layer3))
#             all_issues.extend(layer3)
#         except Exception as exc:
#             logger.error("Page %s | Layer 3 crashed: %s", page_num, exc, exc_info=True)

#     logger.info("grammar_checker: %d total issues across all pages.", len(all_issues))
#     return all_issues

"""
modules/grammar_checker.py
==========================
3-layer grammar & academic-style checker for the AI-Powered Research Paper Checker.

Public API
----------
    check_grammar(parsed_data: dict | list) -> list[dict]
    assemble_doc_from_spans(spans: list[dict]) -> dict

Issue schema
------------
    {
        "id":         str,
        "category":   "grammar",
        "severity":   "critical" | "warning" | "info",
        "page":       int | None,
        "snippet":    str | None,
        "message":    str,
        "suggestion": str,
    }
"""

from __future__ import annotations

import logging
import re
import importlib
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LanguageTool noisy rule blocklist
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
    "WORD_CONTAINS_UNDERSCORE",
    "UNPAIRED_BRACKETS",
    "PUNCTUATION_SPACE",
    "COMMA_COMPOUND_SENTENCE",
    "AGREEMENT_SENT",
    "EN_A_VS_AN",
    "NEEDLESS_VARIANT",
    "HYPHENATED_WORDS_COMPOUNDS",
    "UNNECESSARY_HYPHEN",
    # Fires on author names and place names in citations
    "PROPER_NOUN_SPELLING",
    # Fires on "labour", "organisation" etc. — British vs American variants
    # are style choices, not errors in an international paper
    "BRITISH_ENGLISH_SPELLING",
    "EN_GB_SIMPLE_REPLACE",
    # Comma-before-and rules fire constantly on list sentences
    "COMMA_BEFORE_AND",
    "COMMA_BEFORE_AND_SENT",
    # Fires on hyphenated compounds that vary by style guide
    "EN_COMPOUNDS",
    # Fires on abbreviations like "e.g." and "i.e."
    "E_G",
    "I_E",
}

# ---------------------------------------------------------------------------
# Normalizer patterns
# ---------------------------------------------------------------------------
# References / Bibliography section — strip everything from here on
_REF_SECTION_STRICT = re.compile(
    r"(?:(?:^|\n)\s*)(?:REFERENCES|References|BIBLIOGRAPHY|Bibliography|Works\s+Cited)(?=\s*(?:\n|$))",
)
_REF_SECTION_FALLBACK = re.compile(
    r"(?<!\w)(?:REFERENCES|BIBLIOGRAPHY)(?!\s+\w)",
)

# Acknowledgements section — skip this too (contains first-person "I would like")
_ACK_SECTION_RE = re.compile(
    r"(?:(?:^|\n)\s*)(?:ACKNOWLEDGEMENT?S?|Acknowledgement?s?)(?=\s*(?:\n|$))",
)

_DOI_RE           = re.compile(r'\bdoi:\s*\S+', re.IGNORECASE)
_URL_RE           = re.compile(r'https?://\S+')
_EQUATION_RE      = re.compile(r'\$[^$]+\$|\\\([^)]+\\\)|\\\[[^\]]+\\\]')
_CITATION_TAG_RE  = re.compile(r'\[[\d,\-\s]+\]|\([A-Za-z][A-Za-z\s\-&]+,\s*\d{4}[a-z]?\)')
_TABLE_CAPTION_RE = re.compile(r'\b(table|figure|fig\.?)\s+\d+', re.IGNORECASE)
_MATH_TOKENS_RE   = re.compile(r'[=<>≤≥±×÷∑∫∂√∞α-ωΑ-Ω·°]')

# PDF line-break hyphens
_LINEBREAK_HYPHEN_RE       = re.compile(r'(\w)-\n(\w)')
_LINEBREAK_HYPHEN_SPACE_RE = re.compile(r'(\w)- ([a-z])')

# Page header/footer pattern: conference/journal name lines that PyMuPDF
# extracts from every page. These are typically italic lines at the very top
# or bottom of the page that repeat verbatim.
# Strategy: remove lines that are entirely in title case or ALL CAPS and
# contain keywords typical of conference headers.
_HEADER_FOOTER_RE = re.compile(
    r'(?:^|\n)[^\n]{0,120}(?:Conference|Journal|Proceedings|IEEE|ACM|Springer|AAAI|NeurIPS|ICML|CVPR|ICCV)[^\n]{0,120}(?=\n|$)',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Layer 1 patterns
# ---------------------------------------------------------------------------
_REPEATED_WORD_RE = re.compile(r'\b(\w+)\s+\1\b', re.IGNORECASE)

# Allowlist: valid double-word constructions + single math variable letters
# + common two-word proper name components (e.g. "Yi Yi", "Mon Mon")
_REPEATED_WORD_ALLOWLIST: set[str] = {
    "had", "that",
    # single math variable letters
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
}

_CONTRACTION_RE = re.compile(
    r"\b(can't|won't|don't|doesn't|didn't|isn't|aren't|wasn't|weren't|"
    r"it's|i'm|i've|i'd|i'll|we're|we've|we'd|we'll|you're|they're|"
    r"he's|she's|that's|there's|here's|let's|who's|what's)\b",
    re.IGNORECASE,
)
_CONTRACTION_EXPANSIONS: dict[str, str] = {
    "can't": "cannot", "won't": "will not", "don't": "do not",
    "doesn't": "does not", "didn't": "did not", "isn't": "is not",
    "aren't": "are not", "wasn't": "was not", "weren't": "were not",
    "it's": "it is / its", "i'm": "I am", "i've": "I have",
    "i'd": "I would / I had", "i'll": "I will", "we're": "we are",
    "we've": "we have", "we'd": "we would / we had", "we'll": "we will",
    "you're": "you are", "they're": "they are", "he's": "he is / he has",
    "she's": "she is / she has", "that's": "that is / that has",
    "there's": "there is / there has", "here's": "here is",
    "let's": "let us", "who's": "who is / who has", "what's": "what is / what has",
}

_FIRST_PERSON_RE = re.compile(r'\b(I|me|my|myself|we|our|ours|ourselves)\b')

# ---------------------------------------------------------------------------
# Layer 3 patterns
# ---------------------------------------------------------------------------
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
_LT_MAX_CHARS = 3000

_DOMAIN_WORD_ALLOWLIST: set[str] = {
    "romanized",
    "devanagari",
    "hindi",
    "urdu",
    "n-gram",
    "code-mixed",
}

_INTRO_PHRASE_RE = re.compile(
    r'^\s*(For example|For instance)\b(?!\s*,)',
    re.IGNORECASE,
)

_SKIP_SECTION_PATTERN_RE = re.compile(
    r'(references|bibliography|literaturecited|appendix)',
    re.IGNORECASE,
)

_TABLE_BLOCK_PREFIX_RE = re.compile(
    r'^\s*(table|tab\.|fig(?:ure)?\.?)(?:\s|\d|:|$)',
    re.IGNORECASE,
)
_TABLE_DIGIT_DENSITY_THRESHOLD = 0.30

_MATH_PLACEHOLDER = "[MATH]"
_MATH_INLINE_LATEX_RE = re.compile(r'\$(?:\\.|[^$\\])+\$')
_MATH_INDEXED_VARIABLE_RE = re.compile(
    r'(?<!\w)(?:\\?[A-Za-z]+(?:_[A-Za-z0-9]+)+(?:\^\{?[A-Za-z0-9+\-]+\}?)?)(?!\w)'
)
_MATH_OPERATOR_EXPRESSION_RE = re.compile(
    r'(?<!\w)(?:\\?[A-Za-z]+(?:_[A-Za-z0-9]+)?|\d+(?:\.\d+)?)\s*'
    r'(?:\\times|\\cdot|\\pm|\\div|\\leq|\\geq|\\neq|\\approx|[+\-*/=<>^])\s*'
    r'(?:\\?[A-Za-z]+(?:_[A-Za-z0-9]+)?|\d+(?:\.\d+)?)(?!\w)'
)
_MATH_LATEX_COMMAND_RE = re.compile(r'\\[A-Za-z]+(?:\s*\{[^{}]*\}){0,2}')
_MATH_OPERATOR_SEQUENCE_RE = re.compile(
    r'(?:\\times|\\cdot|\\pm|\\div|\\leq|\\geq|\\neq|\\approx|[+\-*/=<>^])'
    r'(?:\s*(?:\\times|\\cdot|\\pm|\\div|\\leq|\\geq|\\neq|\\approx|[+\-*/=<>^]))+'
)
_MATH_PLACEHOLDER_RUN_RE = re.compile(r'(?:\s*\[MATH\]\s*){2,}')
_MATH_MASK_PATTERNS: tuple[re.Pattern[str], ...] = (
    _MATH_INLINE_LATEX_RE,
    _MATH_INDEXED_VARIABLE_RE,
    _MATH_OPERATOR_EXPRESSION_RE,
    _MATH_LATEX_COMMAND_RE,
    _MATH_OPERATOR_SEQUENCE_RE,
)

# ---------------------------------------------------------------------------
# Singleton state
# ---------------------------------------------------------------------------
_lt_tool: Any | None = None
_lt_failed: bool = False


# ===========================================================================
# Private helpers
# ===========================================================================

def _build_issue(*, id: str, severity: str, page: int | None,
                 snippet: str | None, message: str, suggestion: str) -> dict:
    if snippet:
        snippet = snippet.strip()[:120]
    return {"id": id, "category": "grammar", "severity": severity,
            "page": page, "snippet": snippet, "message": message,
            "suggestion": suggestion}


def _get_tool():
    global _lt_tool, _lt_failed
    if _lt_failed:
        return None
    if _lt_tool is not None:
        return _lt_tool
    import time
    for attempt in (1, 2):
        try:
            import language_tool_python
            logger.info("[INFO] Starting LanguageTool (attempt %d/2)...", attempt)
            _lt_tool = language_tool_python.LanguageTool("en-US")
            logger.info("[INFO] LanguageTool ready.")
            return _lt_tool
        except Exception as exc:
            logger.warning("[ERROR] LanguageTool attempt %d/2 failed: %s", attempt, exc)
            if attempt == 1:
                time.sleep(2)
    _lt_failed = True
    logger.warning("[ERROR] LanguageTool unavailable — Layer 2 skipped.")
    return None


def _find_page_for_snippet(snippet: str, parsed_doc: dict) -> int | None:
    if not snippet or not isinstance(parsed_doc, dict):
        return None
    needle = snippet.lower().strip()
    for page in parsed_doc.get("pages", []):
        if needle in (page.get("text") or "").lower():
            return page.get("page_number")
    return None


def _is_equation_residue(text: str) -> bool:
    """True only when text looks like equation residue (operator-heavy non-prose)."""
    stripped = text.strip()
    if not stripped:
        return False

    # Require explicit math operators so normal numeric prose is preserved.
    if not re.search(r'[=+\-/*^]', stripped):
        return False

    non_alpha = sum(1 for c in stripped if (not c.isalpha() and not c.isspace()))
    non_alpha_ratio = non_alpha / max(len(stripped), 1)
    return non_alpha_ratio >= 0.45


def _split_text_blocks(text: str) -> list[str]:
    """Split page text into analysis blocks while preserving order."""
    normalized = (text or "").replace("\r\n", "\n")
    blocks = [blk.strip() for blk in re.split(r'\n{2,}', normalized) if blk.strip()]
    if len(blocks) <= 1:
        blocks = [blk.strip() for blk in normalized.split('\n') if blk.strip()]
    return blocks


def _is_heading_like(block: str) -> bool:
    first = block.strip().splitlines()[0].strip() if block.strip() else ""
    if not first or len(first) > 90:
        return False
    if not re.match(r'^(?:\d+(?:\.\d+)*\s+)?[A-Za-z]', first):
        return False
    if re.search(r'[.!?]', first):
        return False
    words = first.split()
    if len(words) > 10:
        return False
    if first.isupper():
        return True
    if re.match(r'^\d+(?:\.\d+)*\s+[A-Z][A-Za-z0-9\-\s]+$', first):
        return True
    return first.istitle()


# Pattern to detect a references/bibliography heading even when it appears
# as a word boundary in a short block (handles two-column PDF extraction).
_SKIP_HEADING_RE = re.compile(
    r"(?:^|\n)\s*"
    r"(REFERENCES|References|BIBLIOGRAPHY|Bibliography|"
    r"ACKNOWLEDGEMENT?S?|Acknowledgement?s?|APPENDIX|Appendix|Appendices)"
    r"\s*(?:\n|$)",
)

def _is_skip_section(text: str) -> bool:
    """
    Return True if this text block is (or starts with) a section we should
    stop grammar checking at: References, Bibliography, Acknowledgements, Appendix.

    Handles two forms:
    1. Exact-case heading on its own line (after assemble_doc_from_spans inserts \n).
    2. Aggressively normalised short block (handles "R e f e r-ences" artifacts).
    """
    raw_text = text or ""
    stripped = raw_text.strip()
    if not stripped:
        return False

    # Form 1: heading on its own line (primary path — works after the \n fix)
    if _SKIP_HEADING_RE.search(stripped):
        logger.info("HARD STOP: heading detected in block: %r", stripped[:60])
        return True

    # Form 2: short block whose letters (only) spell a heading keyword
    # Handles OCR artifacts like "R e f e r-ences" or "REFERENCES."
    if len(stripped) < 40:
        clean_look = re.sub(r'[^A-Za-z]+', '', stripped).lower()
        if clean_look in {"references", "bibliography", "appendix", "appendices",
                          "acknowledgement", "acknowledgements",
                          "acknowledgment", "acknowledgments"}:
            logger.info("HARD STOP: normalised heading detected: %r", stripped[:60])
            return True

    return False


def _is_table_block(text: str, digit_density_threshold: float = _TABLE_DIGIT_DENSITY_THRESHOLD) -> bool:
    """
    Return True when the block is likely a table/figure caption or data-heavy row.

    Signals:
    - Starts with Table / Tab. / Fig / Figure.
    - Digit density exceeds configurable threshold.
    """
    stripped = (text or "").strip()
    if not stripped:
        return False

    if _TABLE_BLOCK_PREFIX_RE.match(stripped):
        return True

    digit_count = sum(1 for ch in stripped if ch.isdigit())
    return (digit_count / len(stripped)) > digit_density_threshold


def _mask_math_expressions(text: str) -> str:
    """
    Replace math-heavy spans with a neutral placeholder so sentence structure
    is preserved for grammar checks.
    """
    if not text:
        return ""

    masked = text
    for pattern in _MATH_MASK_PATTERNS:
        masked = pattern.sub(f" {_MATH_PLACEHOLDER} ", masked)

    masked = _MATH_PLACEHOLDER_RUN_RE.sub(f" {_MATH_PLACEHOLDER} ", masked)
    masked = re.sub(rf'\s*{re.escape(_MATH_PLACEHOLDER)}\s*([,.;:!?])',
                    rf' {_MATH_PLACEHOLDER}\1', masked)
    masked = re.sub(r'[ \t]{2,}', ' ', masked)
    return masked.strip()


def _is_non_prose_block(text: str) -> bool:
    """
    Detect table/math-like blocks to avoid grammar checks on non-prose content.

    Signals:
    - high numeric density,
    - many special symbols,
    - lack of sentence punctuation for sizable blocks.
    """
    stripped = text.strip()
    if not stripped:
        return True

    words = re.findall(r'[A-Za-z]+(?:-[A-Za-z]+)?', stripped)
    numbers = re.findall(r'\b\d+(?:\.\d+)?%?\b', stripped)
    special_symbols = re.findall(r'[∆%\[\]{}<>_=+^|~]', stripped)
    has_sentence_punctuation = bool(re.search(r'[.!?]', stripped))

    number_to_word_ratio = len(numbers) / max(len(words), 1)
    symbol_density = len(special_symbols) / max(len(stripped), 1)

    if not words and len(numbers) >= 3:
        return True

    if number_to_word_ratio >= 0.65 and len(special_symbols) >= 2:
        return True
    if len(special_symbols) >= 5 and not has_sentence_punctuation:
        return True
    if not has_sentence_punctuation and len(words) >= 12:
        return True
    if symbol_density > 0.12 and number_to_word_ratio > 0.35:
        return True

    return False


def _table_matrix_metrics(text: str) -> dict[str, float | int | bool]:
    raw = text or ""
    length = max(len(raw), 1)
    alpha_chars = sum(1 for c in raw if c.isalpha())
    digit_chars = sum(1 for c in raw if c.isdigit())
    newline_chars = raw.count("\n")
    symbol_chars = len(re.findall(r'[\[\]∆|\\/\-_=+<>%]', raw))
    has_sentence_punctuation = bool(re.search(r'[.!?]', raw))

    alpha_to_numeric_ratio = alpha_chars / max(digit_chars, 1)
    newline_density = newline_chars / length
    symbol_density = symbol_chars / length
    alpha_density = alpha_chars / length
    digit_density = digit_chars / length

    # Higher is more prose-like; lower is more table/matrix-like.
    prose_density = (
        alpha_density
        - (1.10 * digit_density)
        - (1.40 * symbol_density)
        - (2.80 * newline_density)
    )

    return {
        "alpha_to_numeric_ratio": alpha_to_numeric_ratio,
        "newline_density": newline_density,
        "symbol_density": symbol_density,
        "prose_density": prose_density,
        "has_sentence_punctuation": has_sentence_punctuation,
        "alpha_chars": alpha_chars,
        "digit_chars": digit_chars,
        "symbol_chars": symbol_chars,
        "newline_chars": newline_chars,
    }


def _is_table_matrix_block(text: str) -> tuple[bool, dict[str, float | int | bool]]:
    """Classify whether a block is table/matrix-like using prose-density signals."""
    metrics = _table_matrix_metrics(text)
    raw = (text or "").strip()

    if not raw:
        return False, metrics

    row_like_lines = 0
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        nums = len(re.findall(r'\d+(?:\.\d+)?%?', line))
        words = len(re.findall(r'[A-Za-z]+', line))
        if nums >= 3 and words <= 3:
            row_like_lines += 1

    matrix_pattern = bool(re.search(r'(?:\[[^\]]+\]\s*){2,}', raw))
    dense_numeric_row_pattern = bool(re.search(r'(?:\d+(?:\.\d+)?\s+){5,}\d+(?:\.\d+)?', raw))

    alpha_to_numeric_ratio = float(metrics["alpha_to_numeric_ratio"])
    newline_density = float(metrics["newline_density"])
    symbol_density = float(metrics["symbol_density"])
    prose_density = float(metrics["prose_density"])
    digit_chars = int(metrics["digit_chars"])
    symbol_chars = int(metrics["symbol_chars"])
    has_sentence_punctuation = bool(metrics["has_sentence_punctuation"])

    is_table = (
        matrix_pattern
        or dense_numeric_row_pattern
        or row_like_lines >= 2
        or (
            alpha_to_numeric_ratio < 1.40
            and (newline_density > 0.020 or symbol_density > 0.030)
        )
        or (
            prose_density < 0.15
            and (digit_chars >= 8 or symbol_chars >= 6)
        )
    )

    # Avoid over-filtering normal prose with a few numbers.
    if (
        is_table
        and not matrix_pattern
        and not dense_numeric_row_pattern
        and has_sentence_punctuation
        and alpha_to_numeric_ratio > 1.80
        and symbol_density < 0.040
        and newline_density < 0.020
    ):
        is_table = False

    return is_table, metrics


def _offset_to_page(offset: int, page_spans: list[tuple[int, int, int]]) -> int | None:
    if not page_spans:
        return None
    for start, end, page_num in page_spans:
        if start <= offset < end:
            return page_num
    if offset >= page_spans[-1][1]:
        return page_spans[-1][2]
    return page_spans[0][2]


def _build_document_stream(parsed_doc: dict) -> tuple[str, list[tuple[int, int, int]], dict[str, Any]]:
    """
    Build one combined prose stream for cross-page grammar checks.

    Returns:
    - combined prose text,
    - offset-to-page spans as (start, end, page_num),
    - lightweight stats for logging.
    """
    chunks: list[str] = []
    page_spans: list[tuple[int, int, int]] = []
    cursor = 0
    skip_from_here = False
    stats = {
        "total_blocks": 0,
        "skipped_section_blocks": 0,
        "skipped_table_blocks": 0,
        "skipped_non_prose_blocks": 0,
        "prose_blocks": 0,
        "hard_stop_trigger_page": None,
        "stream_metadata": [],
    }

    for page_data in parsed_doc.get("pages", []):
        page_num = page_data.get("page_number")
        raw_text = page_data.get("text", "") or ""
        if not raw_text.strip():
            continue

        blocks = _split_text_blocks(raw_text)

        # Hard-stop persistence: once triggered, skip every remaining block/page.
        if skip_from_here:
            stats["skipped_section_blocks"] += len(blocks)
            continue

        for block in blocks:
            stats["total_blocks"] += 1

            if skip_from_here:
                stats["skipped_section_blocks"] += 1
                continue

            if _is_table_block(block):
                stats["skipped_table_blocks"] += 1
                stats["stream_metadata"].append({
                    "page": page_num,
                    "is_table": True,
                    "included_in_stream": False,
                    "prose_density": None,
                    "alpha_to_numeric_ratio": None,
                    "newline_density": None,
                    "symbol_density": None,
                    "snippet": block.strip()[:120],
                })
                continue

            # Robust heading detection for noisy extraction:
            # 1) test the whole block,
            # 2) then test short candidate lines near the start of the block.
            block_lines = [line.strip() for line in block.splitlines() if line.strip()]
            heading_candidates = [block]
            heading_candidates.extend(block_lines[:6])

            if any(_is_skip_section(candidate) for candidate in heading_candidates):
                skip_from_here = True
                stats["skipped_section_blocks"] += 1
                stats["hard_stop_trigger_page"] = page_num
                stats["stream_metadata"].append({
                    "page": page_num,
                    "is_table": False,
                    "included_in_stream": False,
                    "is_skip_section": True,
                    "snippet": block.strip()[:120],
                })
                continue

            is_table, table_metrics = _is_table_matrix_block(block)
            if is_table:
                stats["skipped_table_blocks"] += 1
                stats["stream_metadata"].append({
                    "page": page_num,
                    "is_table": True,
                    "included_in_stream": False,
                    "prose_density": round(float(table_metrics["prose_density"]), 4),
                    "alpha_to_numeric_ratio": round(float(table_metrics["alpha_to_numeric_ratio"]), 4),
                    "newline_density": round(float(table_metrics["newline_density"]), 4),
                    "symbol_density": round(float(table_metrics["symbol_density"]), 4),
                    "snippet": block.strip()[:120],
                })
                continue

            cleaned = _normalize_for_grammar(block)
            if not cleaned:
                continue

            fragments = _split_sentences(cleaned) or [cleaned]
            kept_any_fragment = False
            for fragment in fragments:
                fragment = fragment.strip()
                if not fragment:
                    continue

                if _is_heading_like(fragment):
                    continue

                if _is_non_prose_block(fragment):
                    stats["skipped_non_prose_blocks"] += 1
                    stats["stream_metadata"].append({
                        "page": page_num,
                        "is_table": False,
                        "included_in_stream": False,
                        "prose_density": None,
                        "alpha_to_numeric_ratio": None,
                        "newline_density": None,
                        "symbol_density": None,
                        "snippet": fragment[:120],
                    })
                    continue

                if chunks:
                    chunks.append(" ")
                    cursor += 1

                start = cursor
                chunks.append(fragment)
                cursor += len(fragment)
                end = cursor

                page_spans.append((start, end, page_num))
                stats["stream_metadata"].append({
                    "page": page_num,
                    "is_table": False,
                    "included_in_stream": True,
                    "prose_density": round(float(table_metrics["prose_density"]), 4),
                    "alpha_to_numeric_ratio": round(float(table_metrics["alpha_to_numeric_ratio"]), 4),
                    "newline_density": round(float(table_metrics["newline_density"]), 4),
                    "symbol_density": round(float(table_metrics["symbol_density"]), 4),
                    "snippet": fragment[:120],
                })
                kept_any_fragment = True

            if kept_any_fragment:
                stats["prose_blocks"] += 1

    return "".join(chunks), page_spans, stats


def _strip_context_word(context: str, offset: int, length: int) -> str | None:
    """
    Extract the actual flagged word from LanguageTool's context string.
    Falls back to context snippet if offset math fails.
    """
    try:
        word = context[offset: offset + length].strip()
        return word if word else None
    except Exception:
        return context.strip()[:80] if context else None


def _normalize_domain_token(token: str) -> str:
    return token.strip().strip(".,;:!?()[]{}\"'").lower()


def _is_domain_allowlisted(word: str | None) -> bool:
    if not word:
        return False
    normalized = _normalize_domain_token(word)
    if not normalized:
        return False
    if normalized in _DOMAIN_WORD_ALLOWLIST:
        return True
    # Accept equivalent spacing/hyphen forms (e.g. code mixed vs code-mixed).
    if normalized.replace(" ", "-") in _DOMAIN_WORD_ALLOWLIST:
        return True
    if normalized.replace("-", " ") in {w.replace("-", " ") for w in _DOMAIN_WORD_ALLOWLIST}:
        return True
    return False


def _is_likely_acronym_or_name(word: str | None) -> bool:
    """Filter technical terms/acronyms that should not be flagged as spelling noise."""
    if not word:
        return False

    # Explicit domain whitelist.
    if _is_domain_allowlisted(word):
        return True

    # All-caps words >= 2 chars: acronyms (NLP, LSTM, IEEE...).
    if word.isupper() and len(word) >= 2:
        return True

    # Contains digits: model names, years (ResNet50, BERT2...)
    if any(c.isdigit() for c in word):
        return True

    # Contains underscore: variable/method names
    if '_' in word:
        return True

    # Single letter — almost always a variable in academic text
    if len(word) == 1 and word.isalpha():
        return True

    # Intentionally do not ignore tokens solely for being capitalized.
    return False


def _split_sentences(text: str) -> list[str]:
    """Split sentences robustly with abbreviation handling."""
    if not text.strip():
        return []

    try:
        nltk_tokenize = importlib.import_module("nltk.tokenize")
        nltk_punkt = importlib.import_module("nltk.tokenize.punkt")

        punkt_params = nltk_punkt.PunktParameters()
        punkt_params.abbrev_types = {
            "e.g", "i.e", "fig", "al", "et", "etc", "dr", "mr", "mrs", "prof"
        }
        tokenizer = nltk_tokenize.PunktSentenceTokenizer(punkt_params)
        sentences = [s.strip() for s in tokenizer.tokenize(text) if s.strip()]
        if sentences:
            return sentences
    except Exception:
        pass

    placeholders = {
        "e.g.": "__ABBR_E_G__",
        "i.e.": "__ABBR_I_E__",
        "et al.": "__ABBR_ET_AL__",
        "Fig.": "__ABBR_FIG__",
        "fig.": "__ABBR_FIG_LOWER__",
    }
    protected = text
    for source, marker in placeholders.items():
        protected = protected.replace(source, marker)

    parts = [s.strip() for s in re.split(r'(?<=[.?!])\s+', protected) if s.strip()]
    restored: list[str] = []
    for sentence in parts:
        restored_sentence = sentence
        for source, marker in placeholders.items():
            restored_sentence = restored_sentence.replace(marker, source)
        restored.append(restored_sentence)
    return restored


def _split_sentences_with_offsets(text: str) -> list[tuple[str, int, int]]:
    """Return (sentence, start, end) tuples for page mapping."""
    if not text.strip():
        return []

    try:
        nltk_tokenize = importlib.import_module("nltk.tokenize")
        nltk_punkt = importlib.import_module("nltk.tokenize.punkt")
        punkt_params = nltk_punkt.PunktParameters()
        punkt_params.abbrev_types = {
            "e.g", "i.e", "fig", "al", "et", "etc", "dr", "mr", "mrs", "prof"
        }
        tokenizer = nltk_tokenize.PunktSentenceTokenizer(punkt_params)
        spans = list(tokenizer.span_tokenize(text))
        if spans:
            return [(text[start:end].strip(), start, end) for start, end in spans if text[start:end].strip()]
    except Exception:
        pass

    sentences = _split_sentences(text)
    results: list[tuple[str, int, int]] = []
    cursor = 0
    for sentence in sentences:
        start = text.find(sentence, cursor)
        if start == -1:
            start = cursor
        end = start + len(sentence)
        results.append((sentence, start, end))
        cursor = end
    return results


def _is_target_grammar_rule(rule_id: str, issue_type: str, message: str) -> bool:
    """Allow only grammar-focused LanguageTool categories requested by product."""
    rule_upper = (rule_id or "").upper()
    message_lower = (message or "").lower()

    incorrect_word_forms = (
        issue_type == "misspelling"
        and "PROPER_NOUN" not in rule_upper
        and (
            "MORFOLOGIK" in rule_upper
            or "SPELL" in rule_upper
            or "word form" in message_lower
            or "inflection" in message_lower
        )
    )

    subject_verb = (
        "AGREEMENT" in rule_upper
        or "subject-verb" in message_lower
        or "agreement" in message_lower
    )
    punctuation = (
        "PUNCTUATION" in rule_upper
        or "COMMA" in rule_upper
        or "APOSTROPHE" in rule_upper
        or "QUOTE" in rule_upper
        or "punctuation" in message_lower
    )
    capitalization = (
        "UPPERCASE" in rule_upper
        or "LOWERCASE" in rule_upper
        or "CAPITAL" in rule_upper
        or "capital" in message_lower
    )
    missing_articles = (
        "A_VS_AN" in rule_upper
        or "ARTICLE" in rule_upper
        or "article" in message_lower
    )
    return any([
        subject_verb,
        punctuation,
        capitalization,
        missing_articles,
        incorrect_word_forms,
    ])


def _normalize_for_grammar(text: str) -> str:
    """
    Strip non-prose content before any layer sees the text.

    Steps:
    1. Fix PDF line-break hyphens ("pro-\\ncedure" → "procedure")
    2. Strip page headers/footers (conference name lines)
    3. Strip DOIs, URLs
    4. Strip citation tags
    5. Strip table/figure labels
    6. Mask math expressions with a neutral placeholder
    7. Collapse whitespace
    """
    # 1. Fix line-break hyphens
    text = _LINEBREAK_HYPHEN_RE.sub(r'\1\2', text)
    text = _LINEBREAK_HYPHEN_SPACE_RE.sub(r'\1\2', text)

    # Ensure a space after punctuation boundaries (e.g. ").Other" -> "). Other").
    text = re.sub(r'([)\].,;:!?])([A-Za-z])', r'\1 \2', text)

    # 2. Strip page header/footer lines (conference name repeating on every page)
    text = _HEADER_FOOTER_RE.sub(' ', text)

    # 3-7. Standard stripping + masking
    text = _DOI_RE.sub(' ', text)
    text = _URL_RE.sub(' ', text)
    text = _CITATION_TAG_RE.sub(' ', text)
    text = _TABLE_CAPTION_RE.sub(' ', text)
    text = _mask_math_expressions(text)

    # 8. Collapse whitespace
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


# ===========================================================================
# Layer 1 – Heuristic checks
# ===========================================================================

def _heuristic_checks(text: str, page_spans: list[tuple[int, int, int]]) -> list[dict]:
    issues: list[dict] = []

    for sentence, start, _ in _split_sentences_with_offsets(text):
        if _is_equation_residue(sentence):
            continue

        page = _offset_to_page(start, page_spans)
        words = sentence.split()
        if len(words) > 45:
            issues.append(_build_issue(
                id="grammar-heuristic-long-sentence",
                severity="info",
                page=page,
                snippet=sentence[:120],
                message=f"Sentence is {len(words)} words long (recommended max: 45).",
                suggestion="Break into shorter sentences for readability.",
            ))

        marker = _INTRO_PHRASE_RE.match(sentence)
        if marker:
            phrase = marker.group(1)
            issues.append(_build_issue(
                id="grammar-heuristic-missing-comma-intro-phrase",
                severity="warning",
                page=page,
                snippet=sentence[:120],
                message=f"Missing comma after introductory phrase '{phrase}'.",
                suggestion=f"Add a comma after '{phrase}'.",
            ))

    return issues


# ===========================================================================
# Layer 2 – LanguageTool
# ===========================================================================

def _languagetool_checks(text: str, page_spans: list[tuple[int, int, int]]) -> list[dict]:
    tool = _get_tool()
    if tool is None:
        return []

    issues: list[dict] = []
    if not text.strip():
        return issues

    estimated_chunks = (len(text) + _LT_MAX_CHARS - 1) // _LT_MAX_CHARS
    max_issues = _LT_MAX_ISSUES * max(1, estimated_chunks)
    chunk_start = 0

    while chunk_start < len(text):
        chunk_end = min(chunk_start + _LT_MAX_CHARS, len(text))
        if chunk_end < len(text):
            boundary = text.rfind(" ", chunk_start, chunk_end)
            if boundary > chunk_start + 500:
                chunk_end = boundary

        if chunk_end <= chunk_start:
            chunk_end = min(chunk_start + _LT_MAX_CHARS, len(text))

        chunk_text = text[chunk_start:chunk_end]

        try:
            matches = tool.check(chunk_text)
        except Exception as exc:
            logger.warning("grammar_checker: LanguageTool.check() failed: %s", exc)
            chunk_start = chunk_end
            continue

        for match in matches:
            if len(issues) >= max_issues:
                break

            rule_id = getattr(match, "ruleId", "") or "general"
            issue_type = getattr(match, "ruleIssueType", "") or ""
            message = getattr(match, "message", "LanguageTool flagged an issue.")

            if rule_id in NOISY_LT_RULE_IDS and not _is_target_grammar_rule(rule_id, issue_type, message):
                continue

            if not _is_target_grammar_rule(rule_id, issue_type, message):
                continue

            severity = "critical" if issue_type == "misspelling" else "warning"
            replacements = getattr(match, "replacements", []) or []
            suggestion = (f"Try: {', '.join(replacements[:2])}"
                          if replacements else "Review sentence structure.")

            context = getattr(match, "context", "") or ""
            offset = getattr(match, "offsetInContext", 0) or 0
            length = getattr(match, "errorLength", 1) or 1
            global_offset = chunk_start + (getattr(match, "offset", 0) or 0)

            # Extract the actual flagged word FIRST, before any other decision
            word = _strip_context_word(context, offset, length)

            # Explicit domain whitelist: do not report these tokens as errors.
            if _is_domain_allowlisted(word):
                continue

            if _is_likely_acronym_or_name(word):
                logger.debug("Skipping likely acronym/name/citation: %r", word)
                continue

            # If word is very short (1-3 chars), skip — usually a variable
            if word and re.match(r'^[a-zA-Z\d]{1,3}$', word):
                continue

            # Build snippet: use real word if available, else context fragment
            snippet = word if (word and word not in {".", ",", "!", "?", "(", ")"}) \
                      else (context.strip()[:80] if context else None)

            issues.append(_build_issue(
                id=f"grammar-lt-{rule_id.lower()}",
                severity=severity,
                page=_offset_to_page(global_offset, page_spans),
                snippet=snippet,
                message=message,
                suggestion=suggestion,
            ))

        if len(issues) >= max_issues:
            break

        chunk_start = chunk_end

    return issues


# ===========================================================================
# Layer 3 – Academic style checks
# ===========================================================================

def _academic_style_checks(text: str, page: int | None) -> list[dict]:
    # Layer 3 retained for architecture compatibility, but style checks are disabled
    # to return grammar-only issues.
    return []


def _append_unique_issues(
    bucket: list[dict],
    new_issues: list[dict],
    seen_issues: set[tuple[str, str]],
) -> None:
    for issue in new_issues:
        issue_id = str(issue.get("id", ""))
        snippet = str(issue.get("snippet") or "").strip()
        key = (issue_id, snippet)
        if key in seen_issues:
            continue
        seen_issues.add(key)
        bucket.append(issue)


# ===========================================================================
# Data Assembler
# ===========================================================================

# Section-heading words that must appear on their own line so _is_skip_section
# can detect them even in two-column PDFs where spans are space-joined.
_SECTION_HEADING_WORDS: set[str] = {
    "references", "bibliography", "acknowledgement", "acknowledgements",
    "acknowledgment", "acknowledgments", "appendix", "appendices",
}

def assemble_doc_from_spans(spans: list[dict]) -> dict:
    """
    Convert flat span list from pdf_ingestion into page-grouped dict.

    Two-column PDFs: section headings like "References" appear as standalone
    spans mid-stream.  Space-joining them produces "...ranging References from..."
    which _is_skip_section cannot detect (it looks for short, isolated lines).
    Fix: insert a newline marker before any span that is exactly a section heading
    word so it lands on its own line in the assembled text.
    """
    pages_map: dict[int, list[str]] = {}
    for span in spans:
        p_num = span.get("page", 1)
        text  = span.get("text", "")
        if p_num not in pages_map:
            pages_map[p_num] = []
        # If this span is a standalone section heading, give it its own line
        if text.strip().lower() in _SECTION_HEADING_WORDS:
            pages_map[p_num].append("\n" + text.strip() + "\n")
        else:
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
    Main entry point. Iterates page by page, skipping References,
    Acknowledgements, and Appendix sections automatically.

    Parameters
    ----------
    parsed_data : dict | list
        Raw span list from pdf_ingestion (list) or pre-assembled page dict.

    Returns
    -------
    list[dict]  — aggregated issues across all body pages.
    """
    all_issues: list[dict] = []

    if isinstance(parsed_data, list):
        parsed_doc = assemble_doc_from_spans(parsed_data)
        logger.info("Auto-assembled %d spans into %d pages.",
                    len(parsed_data), len(parsed_doc.get("pages", [])))
    else:
        parsed_doc = parsed_data

    if not parsed_doc or "pages" not in parsed_doc:
        logger.warning("grammar_checker: empty or malformed parsed_doc.")
        return all_issues

    seen_issues: set[tuple[str, str]] = set()

    doc_text, page_spans, stats = _build_document_stream(parsed_doc)
    logger.info(
        "grammar stream built: prose=%d, table_skipped=%d, non_prose_skipped=%d, section_skipped=%d, hard_stop_page=%s",
        stats["prose_blocks"],
        stats["skipped_table_blocks"],
        stats["skipped_non_prose_blocks"],
        stats["skipped_section_blocks"],
        stats["hard_stop_trigger_page"],
    )

    if not doc_text.strip():
        logger.info("grammar_checker: no prose content after structural filtering.")
        return all_issues

    original_doc_text = doc_text
    doc_text = _mask_math_expressions(doc_text)
    logger.debug("math masking applied: placeholders=%d", doc_text.count(_MATH_PLACEHOLDER))

    try:
        layer1 = _heuristic_checks(doc_text, page_spans)
        logger.debug("Layer 1: %d", len(layer1))
        _append_unique_issues(all_issues, layer1, seen_issues)
    except Exception as exc:
        logger.error("Layer 1 crashed: %s", exc, exc_info=True)

    try:
        layer2 = _languagetool_checks(doc_text, page_spans)
        logger.debug("Layer 2: %d", len(layer2))
        _append_unique_issues(all_issues, layer2, seen_issues)
    except Exception as exc:
        logger.error("Layer 2 crashed: %s", exc, exc_info=True)

    try:
        layer3 = _academic_style_checks(original_doc_text, None)
        logger.debug("Layer 3: %d", len(layer3))
        _append_unique_issues(all_issues, layer3, seen_issues)
    except Exception as exc:
        logger.error("Layer 3 crashed: %s", exc, exc_info=True)

    logger.info("grammar_checker: %d total issues.", len(all_issues))
    return all_issues