"""
citation_checker.py
--------------------
Checks citation style, consistency, and reference quality in research papers.

Supports:
  - IEEE / CVPR / ICCV  : numeric style  [1], [2-4]
  - APA / Springer      : author-year     (Smith, 2020)
  - MLA                 : author-page     (Smith 45)
  - Chicago             : author-year     (Smith 2020, 45)
  - ACL / NeurIPS / ICML: parenthetical   (Author, Year)

Optional: Crossref API verification (checks if cited papers actually exist).

Author  : <your name>
Module  : citation_checker.py
Project : AI-Powered Research Paper Checker
"""

import re
import time
import requests


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# IEEE: [1]  [2,3]  [1-5]  [1, 3-5]
IEEE_PATTERN = re.compile(r"\[(\d+(?:\s*[,\-]\s*\d+)*)\]")

# APA / ACL: (Smith, 2020)  (Smith & Jones, 2020)  (Smith et al., 2020)
APA_PATTERN = re.compile(
    r"\(([A-Z][A-Za-z\-]+(?:\s+(?:et\s+al\.|&\s+[A-Z][A-Za-z\-]+))?,\s*\d{4}[a-z]?)\)"
)

# MLA: (Smith 45)
MLA_PATTERN = re.compile(r"\(([A-Z][A-Za-z\-]+\s+\d+)\)")

# Chicago: (Smith 2020) or (Smith 2020, 45)
CHICAGO_PATTERN = re.compile(r"\(([A-Z][A-Za-z\-]+\s+\d{4}(?:,\s*\d+)?)\)")

# IEEE reference list entry: [1], [2], etc. at the start of a reference entry.
# NOTE: We do NOT use ^ (line-start anchor) here because pdf_ingestion joins
# all spans with spaces into one long string — there are no newlines, so
# re.MULTILINE anchors never fire. We match [n] preceded by a word boundary
# or whitespace instead.
IEEE_REF_ENTRY_PATTERN = re.compile(r"(?:^|\s)\[(\d+)\]\s+", re.MULTILINE)

# DOI pattern  (10.xxxx/...)
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)

# arXiv identifier
ARXIV_PATTERN = re.compile(r"\barxiv\s*:\s*\d{4}\.\d{4,5}\b", re.IGNORECASE)

# APA reference entry: Author, I. (Year). — again no ^ anchor for same reason.
APA_REF_ENTRY_PATTERN = re.compile(r"(?:^|\s)[A-Z][A-Za-z\-]+,\s+[A-Z].*?\(\d{4}\)", re.MULTILINE)

# ---------------------------------------------------------------------------
# FIX 1 — heading anchor for _get_references_section()
# ---------------------------------------------------------------------------
# The original pattern  r"\bReferences\b"  matches "References" anywhere,
# including inside sentences like "has NO entry in References list."
# We need it to match ONLY when it appears as a standalone section heading.
#
# PDF text extracted by PyMuPDF / pdfplumber is a flat string with real \n
# characters preserved.  A section heading like "References" appears on its
# own line, so it is either:
#   (a) at the very start of the string, OR
#   (b) preceded by a newline  \n
#
# The fixed pattern uses a look-behind:  (?:^|\n)\s*
# which means "at start-of-string OR right after a newline, with optional
# leading whitespace".  re.MULTILINE makes ^ match at each line start,
# so we don't need it in the look-behind — but we keep re.IGNORECASE.
#
# We also require that nothing except whitespace follows on the same "line"
# before a newline or end-of-string, so partial matches like
# "References list" are rejected:
#   (?=\s*(?:\n|$))   — look-ahead: only spaces/tabs before newline or EOS

_REF_HEADING_RE = re.compile(
    r"(?:(?:^|\n)\s*)(?P<heading>References|Bibliography|Works\s+Cited)(?=\s*(?:\n|$))",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helper: build a standardised issue dict
# ---------------------------------------------------------------------------

def _build_issue(
    issue_id: str,
    message: str,
    suggestion: str,
    severity: str = "warning",
    page: int | None = None,
) -> dict:
    """
    Return a structured citation issue.

    Fields mirror those produced by format_checker and grammar_checker so
    report_generator can treat every module's output the same way.
    """
    return {
        "id": issue_id,
        "category": "citations",
        "severity": severity,
        "page": page,
        "message": message,
        "suggestion": suggestion,
        "location": None,
    }


# ---------------------------------------------------------------------------
# Helper: find which page a piece of text appears on
# ---------------------------------------------------------------------------

def _find_page_for_text(parsed_document: list | None, search_text: str) -> int | None:
    """
    Scan the span list from pdf_ingestion.extract_structure() to find which page
    contains search_text.  Returns the page number (int) or None.
    """
    if not parsed_document or not search_text:
        return None

    needle = search_text.strip().lower()
    pages: dict[int, str] = {}
    for span in parsed_document:
        page_num = span.get("page")
        if page_num is None:
            continue
        span_text = (span.get("text") or "").lower()
        pages[page_num] = pages.get(page_num, "") + " " + span_text

    for page_num in sorted(pages.keys()):
        if needle in pages[page_num]:
            return page_num

    return None


# ---------------------------------------------------------------------------
# Helper: extract the References section text  (FIX 1 applied here)
# ---------------------------------------------------------------------------

def _get_references_section(full_text: str) -> str:
    """
    Return the portion of full_text from the 'References' heading onwards.
    Returns empty string if no References section is found.

    FIX: Uses _REF_HEADING_RE which requires the heading to be on its own
    line, preventing false matches on phrases like "entry in References list."
    """
    match = _REF_HEADING_RE.search(full_text)
    if match:
        return full_text[match.start():]
    return ""


# ---------------------------------------------------------------------------
# Helper: expand IEEE range token → list of ints
# ---------------------------------------------------------------------------

def _expand_ieee_token(token: str) -> list[int]:
    """
    Expand a raw IEEE citation token into individual reference numbers.

    Examples:
        "1"      → [1]
        "1,3"    → [1, 3]
        "1-3"    → [1, 2, 3]
        "1, 3-5" → [1, 3, 4, 5]
    """
    result = []
    for part in [p.strip() for p in token.split(",") if p.strip()]:
        if "-" in part:
            bounds = [b.strip() for b in part.split("-")]
            if len(bounds) == 2 and bounds[0].isdigit() and bounds[1].isdigit():
                start, end = int(bounds[0]), int(bounds[1])
                if start <= end:
                    result.extend(range(start, end + 1))
        elif part.isdigit():
            result.append(int(part))
    return sorted(set(result))


# ---------------------------------------------------------------------------
# IEEE numeric style checks
# ---------------------------------------------------------------------------

def _check_ieee_style(full_text: str) -> list[dict]:
    """
    Validate IEEE numeric citation style.

    Checks:
      1. At least one [n] citation exists in the body text.
      2. Citations start at [1] (not [2] or higher).
      3. A numbered reference list exists.
      4. Every in-text citation number has a matching reference entry.
      5. No gaps in the reference list numbering.
      6. References are not cited out of order.
    """
    issues = []

    # Split body vs references using the FIXED heading detector.
    ref_section = _get_references_section(full_text)
    if ref_section:
        ref_match = _REF_HEADING_RE.search(full_text)
        body_text = full_text[:ref_match.start()]
    else:
        body_text = full_text

    # --- Check 1: any IEEE citations in the body? ---
    tokens = IEEE_PATTERN.findall(body_text)
    if not tokens:
        issues.append(_build_issue(
            issue_id="ieee-no-citations",
            message="No IEEE-style numeric citations like [1] found in the paper body.",
            suggestion="Use bracketed numbers [1], [2], … in the text to cite references.",
            severity="warning",
        ))
        return issues

    # Build flat list of cited numbers in order of first appearance
    cited_in_order = []
    seen = set()
    for token in tokens:
        for num in _expand_ieee_token(token):
            if num not in seen:
                cited_in_order.append(num)
                seen.add(num)

    unique_cited = sorted(seen)

    # --- Check 2: start at [1]? ---
    if unique_cited[0] != 1:
        issues.append(_build_issue(
            issue_id="ieee-start-not-one",
            message=f"IEEE citations start at [{unique_cited[0]}] instead of [1].",
            suggestion="Number citations from [1] in the order they first appear in the text.",
            severity="info",
        ))

    # --- Check 3: reference list exists? ---
    if not ref_section:
        issues.append(_build_issue(
            issue_id="ieee-no-ref-section",
            message="No 'References' section found in the paper.",
            suggestion="Add a References section at the end listing all cited works.",
            severity="error",
        ))
        return issues

    # FIX 2 — extract ONLY the actual numbered entries from the ref list.
    # The old approach picked up every [n] in ref_section, including [n]
    # tokens inside the annotation comments planted in this PDF.
    # Fix: only count [n] when it is immediately followed by an author name
    # (capital letter after the bracket), which is the IEEE entry format:
    #   [1] A. Vaswani, ...
    # Pattern: optional whitespace, [digits], whitespace, capital letter
    IEEE_REAL_ENTRY_RE = re.compile(r"(?:^|\n)\s*\[(\d+)\]\s+[A-Z]", re.MULTILINE)
    ref_numbers = sorted(set(int(n) for n in IEEE_REAL_ENTRY_RE.findall(ref_section)))

    if not ref_numbers:
        issues.append(_build_issue(
            issue_id="ieee-ref-list-empty",
            message="References section exists but no numbered entries like [1] were found.",
            suggestion="Format each reference as:  [1] A. Author, 'Title,' Journal, vol. 1, 2020.",
            severity="error",
        ))
        return issues

    # --- Check 4: every in-text citation has a reference entry ---
    missing = [n for n in unique_cited if n not in ref_numbers]
    if missing:
        shown = missing[:8]
        extra = f" (and {len(missing) - 8} more)" if len(missing) > 8 else ""
        issues.append(_build_issue(
            issue_id="ieee-unresolved-citations",
            message=f"Citations {shown}{extra} appear in text but have no entry in References.",
            suggestion="Add the missing reference entries or correct the citation numbers.",
            severity="warning",
        ))

    # --- Check 4b: reference entries never cited ---
    uncited = [n for n in ref_numbers if n not in seen]
    if uncited:
        shown = uncited[:5]
        extra = f" (and {len(uncited) - 5} more)" if len(uncited) > 5 else ""
        issues.append(_build_issue(
            issue_id="ieee-uncited-references",
            message=f"References {shown}{extra} are listed but never cited in the text.",
            suggestion="Either cite these references in the text or remove them from the list.",
            severity="info",
        ))

    # --- Check 5: no gaps in reference list numbering ---
    if ref_numbers:
        expected = list(range(1, max(ref_numbers) + 1))
        gaps = [n for n in expected if n not in ref_numbers]
        if gaps:
            issues.append(_build_issue(
                issue_id="ieee-numbering-gaps",
                message=f"Reference list has gaps in numbering: {gaps[:5]}.",
                suggestion="Use continuous sequential numbering ([1], [2], [3], …) in the References list.",
                severity="info",
            ))

    # --- Check 6: in-text citations in ascending order? ---
    out_of_order_pairs = []
    for i in range(1, len(cited_in_order)):
        if cited_in_order[i] < cited_in_order[i - 1]:
            out_of_order_pairs.append((cited_in_order[i - 1], cited_in_order[i]))
            if len(out_of_order_pairs) >= 3:
                break
    if out_of_order_pairs:
        issues.append(_build_issue(
            issue_id="ieee-citation-order",
            message=f"Citations appear out of order (e.g. {out_of_order_pairs[0]}). "
                    "IEEE numbers citations in the order of first appearance.",
            suggestion="Renumber citations so [1] is the first work cited, [2] the second, etc.",
            severity="info",
        ))

    return issues


# ---------------------------------------------------------------------------
# APA / author-year style checks
# ---------------------------------------------------------------------------

def _check_apa_style(full_text: str) -> list[dict]:
    """Validate APA author-year citation style."""
    issues = []

    hits = APA_PATTERN.findall(full_text)
    if len(hits) < 2:
        issues.append(_build_issue(
            issue_id="apa-few-citations",
            message="Very few APA-style (Author, Year) citations detected.",
            suggestion="Use (Author, Year) format, e.g. (Smith, 2020) or Smith (2020), for all citations.",
            severity="warning",
        ))
        return issues

    if len(hits) > 5 and "et al." not in full_text:
        issues.append(_build_issue(
            issue_id="apa-missing-et-al",
            message="Many citations found but 'et al.' was never used.",
            suggestion="For works with 3 or more authors, use (First Author et al., Year) after the first mention.",
            severity="info",
        ))

    year_hits = re.findall(r",\s*(\d{4})[a-z]?\)", full_text)
    suspicious_years = [y for y in year_hits if int(y) < 1900 or int(y) > 2026]
    if suspicious_years:
        issues.append(_build_issue(
            issue_id="apa-suspicious-year",
            message=f"Suspicious citation year(s) detected: {suspicious_years[:5]}.",
            suggestion="Verify these years are correct in your citations.",
            severity="info",
        ))

    ref_section = _get_references_section(full_text)
    if ref_section:
        apa_entries = APA_REF_ENTRY_PATTERN.findall(ref_section)
        if not apa_entries:
            issues.append(_build_issue(
                issue_id="apa-ref-format",
                message="Reference list entries do not appear to follow APA format.",
                suggestion=(
                    "APA reference format: Author, A. B. (Year). Title of work. Publisher/Journal."
                    " Example: Smith, J. (2020). Deep learning survey. Nature, 5(1), 10-20."
                ),
                severity="warning",
            ))

    return issues


# ---------------------------------------------------------------------------
# Generic citation consistency check
# ---------------------------------------------------------------------------

def _check_citation_consistency(full_text: str) -> list[dict]:
    """Detect which citation style(s) are used and flag mixing."""
    issues = []

    counts = {
        "IEEE [n]":           len(IEEE_PATTERN.findall(full_text)),
        "APA (Author,Year)":  len(APA_PATTERN.findall(full_text)),
        "MLA (Author pg)":    len(MLA_PATTERN.findall(full_text)),
        "Chicago (Author Y)": len(CHICAGO_PATTERN.findall(full_text)),
    }

    active = [style for style, count in counts.items() if count > 1]

    if not active:
        issues.append(_build_issue(
            issue_id="citation-no-style",
            message="No recognizable citation style detected (IEEE, APA, MLA, Chicago).",
            suggestion="Choose a citation style appropriate for your venue and apply it throughout.",
            severity="warning",
        ))
    elif len(active) > 1:
        issues.append(_build_issue(
            issue_id="citation-mixed-styles",
            message=f"Multiple citation styles detected in the same paper: {', '.join(active)}.",
            suggestion="Pick one citation style and apply it consistently throughout the paper.",
            severity="warning",
        ))

    return issues


# ---------------------------------------------------------------------------
# Reference quality checks
# ---------------------------------------------------------------------------

def _check_reference_quality(
    full_text: str,
    standard: str,
    paper_type: str | None = None,
    parsed_document: list | None = None,
) -> list[dict]:
    """Light-weight checks on the overall quality of the reference list."""
    issues = []
    ref_section = _get_references_section(full_text)
    if not ref_section:
        return issues

    ref_lines = [line.strip() for line in ref_section.splitlines() if line.strip()]
    if len(ref_lines) < 4:
        return issues

    if (paper_type or "").strip().lower() in ("arxiv", "arxiv_or_preprint", "preprint"):
        return issues

    doi_count   = len(DOI_PATTERN.findall(ref_section))
    arxiv_count = len(ARXIV_PATTERN.findall(ref_section))
    ref_page    = _find_page_for_text(parsed_document, "references")

    if standard in {"IEEE", "ACL", "CVPR", "ICCV", "SPRINGER", "ELSEVIER"} and doi_count == 0:
        issues.append(_build_issue(
            issue_id="ref-doi-missing",
            message="No DOI links found in the References section.",
            suggestion=(
                "Add DOI links where available. "
                "Most venues prefer references that include a DOI so readers can locate papers easily."
            ),
            severity="info",
            page=ref_page,
        ))

    if arxiv_count >= 3 and doi_count == 0:
        issues.append(_build_issue(
            issue_id="ref-arxiv-heavy",
            message=f"{arxiv_count} arXiv references found with no peer-reviewed DOI entries.",
            suggestion=(
                "Where a published version exists, prefer citing the journal or conference paper "
                "rather than only the arXiv preprint."
            ),
            severity="info",
            page=ref_page,
        ))

    title_lines = [line.lower() for line in ref_lines if len(line) > 30 and not line.startswith("[")]
    seen_titles: set[str] = set()
    duplicates: list[str] = []
    for line in title_lines:
        fingerprint = line[:60].strip()
        if fingerprint in seen_titles:
            duplicates.append(fingerprint[:50])
        seen_titles.add(fingerprint)

    if duplicates:
        issues.append(_build_issue(
            issue_id="ref-duplicates",
            message=f"Possible duplicate reference entries detected ({len(duplicates)} instance(s)).",
            suggestion="Review your References section for repeated entries and remove duplicates.",
            severity="warning",
            page=ref_page,
        ))

    return issues


# ---------------------------------------------------------------------------
# Crossref API verification
# ---------------------------------------------------------------------------

def _verify_reference_via_crossref(title: str, author: str | None = None) -> dict:
    """Query the free Crossref API to check if a cited paper actually exists."""
    time.sleep(0.5)

    params: dict = {
        "query.bibliographic": title,
        "rows": 1,
        "select": "title,author,DOI,score",
    }
    if author:
        params["query.author"] = author

    headers = {
        "User-Agent": "ResearchPaperChecker/1.0 (mailto:your-email@example.com)"
    }

    try:
        response = requests.get(
            "https://api.crossref.org/works",
            params=params,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        items = data.get("message", {}).get("items", [])
        if not items:
            return {"found": False, "doi": None, "score": 0.0, "reason": "No results returned by Crossref"}

        top = items[0]
        score = float(top.get("score", 0))

        if score > 50:
            return {
                "found": True,
                "doi": top.get("DOI", "N/A"),
                "score": score,
                "reason": "High-confidence match found",
            }
        else:
            return {
                "found": False,
                "doi": None,
                "score": score,
                "reason": f"Low-confidence match (score={score:.1f}); paper may not exist or title is different",
            }

    except requests.exceptions.Timeout:
        return {"found": None, "doi": None, "score": 0.0, "reason": "Crossref API timed out"}
    except requests.exceptions.ConnectionError:
        return {"found": None, "doi": None, "score": 0.0, "reason": "Could not connect to Crossref API"}
    except Exception as exc:
        return {"found": None, "doi": None, "score": 0.0, "reason": f"API error: {str(exc)}"}


def _extract_ieee_reference_titles(ref_section: str, max_refs: int = 10) -> list[dict]:
    """
    Extract title strings from IEEE-style reference entries.

    FIX 3 — only split on REAL reference entries (lines that start with [N]
    followed by an author initial, i.e. a capital letter).  The old splitter
    re.split() fragmented the entire text on every [N] token — including
    in-text citations carried over from a bad ref_section split — producing
    garbage titles like "[2]. Encoder-decoder frameworks..."
    """
    # Only match lines that look like:  [1] A. Author, "Title...",
    # i.e. [digits] followed by whitespace and a capital letter (author initial)
    IEEE_REAL_ENTRY_RE = re.compile(r"(?:^|\n)\s*\[(\d+)\]\s+[A-Z]", re.MULTILINE)

    # Split on real entry boundaries only
    entries = IEEE_REAL_ENTRY_RE.split(ref_section)
    # split() with a capturing group returns:  [pre, num, text, num, text, ...]
    # We zip pairs: (num, text)
    results = []
    it = iter(entries)
    next(it)   # skip the pre-match preamble (annotation text before [1])
    for num_str, entry_text in zip(it, it):
        if not num_str.isdigit():
            continue
        ref_number = int(num_str)
        entry_text = entry_text.strip()

        # Extract quoted title
        quote_match = re.search(r'["\u201c\u201d]([^"\u201c\u201d]{10,120})["\u201c\u201d]', entry_text)
        if quote_match:
            title = quote_match.group(1).strip()
        else:
            parts = entry_text.split(",")
            title = ",".join(parts[1:3]).strip()[:120] if len(parts) > 1 else entry_text[:120]

        if len(title) > 10:
            results.append({"number": ref_number, "title": title, "raw": entry_text[:200]})

        if len(results) >= max_refs:
            break

    return results


def _check_references_via_crossref(
    full_text: str,
    max_to_check: int = 8,
) -> list[dict]:
    """Verify a sample of IEEE-style references against the Crossref database."""
    issues = []
    ref_section = _get_references_section(full_text)
    if not ref_section:
        return issues

    refs_to_check = _extract_ieee_reference_titles(ref_section, max_refs=max_to_check)
    if not refs_to_check:
        return issues

    unverified = []
    api_error   = False

    for ref in refs_to_check:
        result = _verify_reference_via_crossref(ref["title"])

        if result["found"] is None:
            api_error = True
            break

        if result["found"] is False:
            unverified.append(ref["number"])

    if api_error:
        issues.append(_build_issue(
            issue_id="crossref-api-unavailable",
            message="Crossref API was unavailable; reference verification was skipped.",
            suggestion="Run the checker again when you have internet access to verify references.",
            severity="info",
        ))
    elif unverified:
        issues.append(_build_issue(
            issue_id="crossref-unverified-refs",
            message=(
                f"References {unverified} could not be confidently verified via Crossref. "
                "This may mean the title is misspelled or the paper does not exist."
            ),
            suggestion=(
                "Double-check these references. Search for them on Google Scholar or doi.org "
                "to confirm they exist and the details are correct."
            ),
            severity="warning",
        ))

    return issues


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def check_citations(
    full_text: str,
    standard: str,
    paper_type: str | None = None,
    parsed_document: list | None = None,
    use_crossref: bool = True,
) -> list[dict]:
    """
    Run all citation checks for the given paper and formatting standard.

    Args:
        full_text       : Complete extracted text of the paper.
        standard        : Formatting standard, e.g. "IEEE", "APA", "ACL", "Springer".
        paper_type      : Optional hint — pass "arxiv_or_preprint" to skip some checks.
        parsed_document : Optional output of pdf_ingestion.py (for page-number lookup).
        use_crossref    : Set to False to skip the Crossref API calls (faster, offline).

    Returns:
        List of issue dicts. Each dict has:
            id, category, severity, page, message, suggestion, location
    """
    issues: list[dict] = []
    std = standard.strip().upper()

    # 1. Venue-specific citation style check
    if std in {"IEEE", "CVPR", "ICCV"}:
        issues.extend(_check_ieee_style(full_text))
    elif std in {"APA", "SPRINGER", "ELSEVIER"}:
        issues.extend(_check_apa_style(full_text))
    elif std == "ACL":
        issues.extend(_check_apa_style(full_text))
    elif std in {"NEURIPS", "ICML", "AAAI"}:
        issues.extend(_check_citation_consistency(full_text))
    else:
        issues.extend(_check_citation_consistency(full_text))

    # 2. Reference quality (DOI, arXiv, duplicates)
    issues.extend(
        _check_reference_quality(full_text, std, paper_type, parsed_document)
    )

    # 3. Crossref API verification
    if use_crossref and std in {"IEEE", "CVPR", "ICCV"}:
        issues.extend(_check_references_via_crossref(full_text))

    # 4. Universal: References section must exist
    if not _get_references_section(full_text):
        issues.append(_build_issue(
            issue_id="citation-no-references-section",
            message="No 'References' section heading found in the document.",
            suggestion="Add a 'References' section at the end of your manuscript.",
            severity="error",
            page=None,
        ))

    # 5. Fill in page numbers for issues that don't have one yet
    ref_page = _find_page_for_text(parsed_document, "references")
    for issue in issues:
        if issue.get("page") is None:
            issue_id = issue.get("id", "")
            if any(keyword in issue_id for keyword in ("ref", "citation", "doi", "arxiv", "crossref")):
                issue["page"] = ref_page

    return issues