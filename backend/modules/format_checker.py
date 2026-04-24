"""
format_checker.py
─────────────────────────────────────────────────────────────────────────────
Single-file module for PDF layout and structural formatting checks.

This module focuses on venue/template compliance (geometry, typography,
sections, captions, and equations). Linguistic/readability checks are handled
in grammar_checker.py.

Pipeline position:
    pdf_ingestion.py  →  [format_checker.py]  →  grammar_checker.py
"""

from __future__ import annotations

import os
import re
from collections import Counter

# Integrated: Importing the official extraction logic from your teammate
from modules.pdf_ingestion import extract_structure

# ── load the standards config ──────────────────────────────────────────────
try:
    from configs.format_rules import STANDARDS, get_standard
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from configs.format_rules import STANDARDS, get_standard


# ─────────────────────────────────────────────────────────────────────────────
# REGEX PATTERNS
# ─────────────────────────────────────────────────────────────────────────────

FIGURE_CAPTION_RE = re.compile(
    r"^\s*(Figure|Fig\.)\s*([0-9]+)\b\s*[:\.]?", re.IGNORECASE
)
TABLE_CAPTION_RE = re.compile(
    r"^\s*Table\s*([0-9]+|[IVXLC]+)\b\s*[:\.]?", re.IGNORECASE
)
IN_TEXT_FIGURE_RE = re.compile(r"\bFigure\s+([0-9]+)\b")
IN_TEXT_FIG_RE    = re.compile(r"\bFig\.\s*([0-9]+)\b")
IN_TEXT_TABLE_RE  = re.compile(r"\bTable\s+([0-9]+|[IVXLC]+)\b")
EQUATION_LABEL_RE = re.compile(r"\((\d+)\)\s*$", re.MULTILINE)
IN_TEXT_EQ_RE = re.compile(
    r"\b(?:Eq\.|equation|Equation)\s*\((\d+)\)", re.IGNORECASE
)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION ALIASES & ORDER
# ─────────────────────────────────────────────────────────────────────────────

SECTION_ALIASES: dict[str, list[str]] = {
    "abstract":     ["abstract"],
    "introduction": ["introduction", "1 introduction", "1. introduction"],
    "references":   ["references", "bibliography"],
    "conclusion":   ["conclusion", "conclusions"],
    "discussion":   ["discussion", "results and discussion"],
    "method":       ["method", "methods", "methodology", "approach"],
    "result":       ["result", "results", "experiments", "evaluation"],
    "limitations":  ["limitations", "limitation"],
    "checklist":    ["checklist", "paper checklist", "reproducibility checklist"],
    "keywords":     ["keywords", "index terms", "key words"],
}

SECTION_ORDER = [
    "abstract", "introduction", "method",
    "result", "discussion", "conclusion", "references",
]


# ═════════════════════════════════════════════════════════════════════════════
# 2.  SHARED HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _resolve_margin(rules: dict, side: str) -> float | None:
    for suffix, scale in [("", 1.0), ("_pts", 1.0), ("_cm", 28.346)]:
        key = f"margin_{side}{suffix}"
        if rules.get(key) is not None:
            return float(rules[key]) * scale
    return None


def _issue(
    issue_id:   str,
    severity:   str,
    page:       int | None,
    message:    str,
    suggestion: str,
    category:   str = "formatting",
    location:   dict | None = None,
) -> dict:
    return {
        "id":         issue_id,
        "category":   category,
        "severity":   severity,
        "page":       page,
        "message":    message,
        "suggestion": suggestion,
        "location":   location,
    }


def _has_section(full_text_lower: str, section_name: str) -> bool:
    return any(
        alias in full_text_lower
        for alias in SECTION_ALIASES.get(section_name, [section_name])
    )


def _find_heading_location(
    parsed_document: dict, section_name: str
) -> tuple[int | None, dict | None]:
    aliases = SECTION_ALIASES.get(section_name, [section_name])
    for page in parsed_document.get("pages", []):
        for line in page.get("heading_candidates", []):
            if any(alias in line.get("text", "").lower() for alias in aliases):
                return page.get("page_number"), {"bbox": line.get("bbox")}
    return None, None


def _last_main_content_page(parsed_document: dict) -> int:
    for page in parsed_document.get("pages", []):
        for line in page.get("heading_candidates", []):
            if "references" in line.get("text", "").strip().lower():
                return max(1, int(page.get("page_number", 1)) - 1)
    return int(parsed_document.get("page_count", 1))


# ═════════════════════════════════════════════════════════════════════════════
# 3.  GEOMETRY CHECKS
# ═════════════════════════════════════════════════════════════════════════════

def _check_page_size(
    page: dict, rules: dict, standard_key: str, is_lenient: bool
) -> list[dict]:
    exp_w = rules.get("page_width_pts")
    exp_h = rules.get("page_height_pts")
    if exp_w is None or exp_h is None:
        return []

    base_tol  = float(rules.get("tolerance_pts", 7.2))
    tolerance = base_tol * 2 if is_lenient else base_tol

    candidates = [[exp_w, exp_h]] + (rules.get("allowed_page_sizes") or [])
    min_delta  = min(
        max(abs(page["width"] - cw), abs(page["height"] - ch))
        for cw, ch in candidates
    )

    if min_delta <= tolerance:
        return []

    sev = "info" if is_lenient else "warning"
    msg = (
        f"Page size ({page['width']:.1f}×{page['height']:.1f} pt) "
        f"differs from {standard_key} template ({exp_w:.1f}×{exp_h:.1f} pt)"
    )
    if is_lenient:
        msg += " — published layouts may differ from submission templates"

    return [_issue(
        issue_id   = f"page-size-{page['page_number']}",
        severity   = sev,
        page       = page["page_number"],
        message    = msg,
        suggestion = "For submissions, use the official template page size.",
        location   = {"bbox": [0, 0, page["width"], page["height"]]},
    )]


def _check_margins(
    page: dict, rules: dict, is_lenient: bool
) -> list[dict]:
    spans = page.get("spans", [])
    if not spans:
        return []

    expected_body_size = rules.get("body_size")
    tol_size = float(rules.get("tolerance_font_size", 0.5)) + 0.5

    if expected_body_size is not None:
        candidates = [
            s for s in spans
            if abs(float(s.get("size", 0)) - float(expected_body_size)) <= tol_size
        ]
        if not candidates:
            candidates = spans
    else:
        candidates = spans

    top_cut    = page["height"] * 0.06
    bottom_cut = page["height"] * 0.94
    body_spans = [s for s in candidates if top_cut <= s["bbox"][1] < bottom_cut]
    if not body_spans:
        body_spans = candidates
    if not body_spans:
        return []

    x0_min = min(s["bbox"][0] for s in body_spans)
    y0_min = min(s["bbox"][1] for s in body_spans)
    x1_max = max(s["bbox"][2] for s in body_spans)
    y1_max = max(s["bbox"][3] for s in body_spans)

    measured = {
        "left":   x0_min,
        "top":    y0_min,
        "right":  page["width"]  - x1_max,
        "bottom": page["height"] - y1_max,
    }

    base_tol  = float(rules.get("tolerance_pts", 7.2))
    tolerance = max(base_tol * 2, 10.0) if is_lenient else base_tol

    issues = []
    for side in ("left", "top", "right", "bottom"):
        expected = _resolve_margin(rules, side)
        if expected is None:
            continue
        if abs(measured[side] - expected) > tolerance:
            sev = "info" if is_lenient else "warning"
            msg = (
                f"{side.capitalize()} margin is {measured[side]:.1f} pt, "
                f"expected {expected:.1f} pt"
            )
            if is_lenient:
                msg += " — published layout may vary"
            issues.append(_issue(
                issue_id   = f"margin-{side}-{page['page_number']}",
                severity   = sev,
                page       = page["page_number"],
                message    = msg,
                suggestion = "Adjust margins to match the selected template.",
                location   = {"bbox": [x0_min, y0_min, x1_max, y1_max]},
            ))
    return issues


def _check_columns(page: dict, rules: dict, standard_key: str) -> list[dict]:
    if int(rules.get("columns", 1)) == 1:
        return []

    lines = page.get("lines", [])
    if len(lines) < 8:
        return []

    mid         = page["width"] / 2
    left_pct    = sum(1 for ln in lines if ln["bbox"][2] <= mid + 10) / len(lines)
    right_pct   = sum(1 for ln in lines if ln["bbox"][0] >= mid - 10) / len(lines)

    if left_pct < 0.35 or right_pct < 0.35:
        return [_issue(
            issue_id   = f"columns-{page['page_number']}",
            severity   = "info",
            page       = page["page_number"],
            message    = (
                f"Two-column layout expected ({standard_key}) but signal is weak "
                f"(left {left_pct:.0%}, right {right_pct:.0%} of lines)"
            ),
            suggestion = f"Verify the document follows the {standard_key} two-column template.",
            location   = {"bbox": [0, 0, page["width"], page["height"]]},
        )]
    return []


# ═════════════════════════════════════════════════════════════════════════════
# 4.  TYPOGRAPHY CHECKS
# ═════════════════════════════════════════════════════════════════════════════

def _check_body_font(
    parsed_document: dict, rules: dict, standard_key: str, strict: bool
) -> list[dict]:
    expected = (rules.get("body_font") or "").lower().strip()
    dominant = (parsed_document.get("dominant_font") or "").lower().strip()
    if not expected or not dominant:
        return []

    families = ["times", "arial", "helvetica", "courier", "computer modern"]
    exp_base = next((f for f in families if f in expected), expected.split()[0])
    dom_base = next((f for f in families if f in dominant), dominant.split()[0])

    if exp_base not in dom_base:
        return [_issue(
            issue_id   = "font-body-mismatch",
            severity   = "warning" if strict else "info",
            page       = None,
            message    = (
                f"Body font is '{parsed_document.get('dominant_font')}', "
                f"but {standard_key} requires '{rules.get('body_font')}'"
            ),
            suggestion = f"Switch body text to {rules.get('body_font')}.",
        )]
    return []


def _check_body_size(
    parsed_document: dict, rules: dict, standard_key: str, strict: bool
) -> list[dict]:
    dom_size  = parsed_document.get("dominant_size")
    exp_size  = rules.get("body_size")
    tolerance = float(rules.get("tolerance_font_size", 0.5))
    if dom_size is None or exp_size is None:
        return []

    min_size = float(rules.get("body_size_min", exp_size))
    max_size = float(rules.get("body_size_max", exp_size))
    if min_size <= float(dom_size) <= max_size:
        return []

    if abs(float(dom_size) - float(exp_size)) > tolerance:
        return [_issue(
            issue_id   = "font-size-body",
            severity   = "warning" if strict else "info",
            page       = None,
            message    = (
                f"Body text size is {dom_size} pt, "
                f"but {standard_key} requires {exp_size} pt (±{tolerance} pt)"
            ),
            suggestion = f"Set body font size to {exp_size} pt.",
        )]
    return []


# ═════════════════════════════════════════════════════════════════════════════
# 5.  STRUCTURE CHECKS
# ═════════════════════════════════════════════════════════════════════════════

def _check_required_sections(
    parsed_document: dict, rules: dict, standard_key: str,
    strict: bool, published: bool,
) -> list[dict]:
    issues: list[dict] = []
    lowered = parsed_document.get("full_text", "").lower()

    for section in rules.get("required_sections", ["abstract", "introduction", "references"]):
        if not _has_section(lowered, section):
            page, loc = _find_heading_location(parsed_document, section)
            issues.append(_issue(
                issue_id   = f"structure-missing-{section}",
                severity   = "info" if (published and not strict) else "warning",
                page       = page,
                message    = f"Section heading '{section.title()}' was not detected.",
                suggestion = f"Add a clearly labelled '{section.title()}' section.",
                category   = "structure",
                location   = loc,
            ))

    if strict:
        for section in rules.get("strict_required_sections", []):
            if not _has_section(lowered, section):
                page, loc = _find_heading_location(parsed_document, section)
                issues.append(_issue(
                    issue_id   = f"structure-required-{section}",
                    severity   = "critical",
                    page       = page,
                    message    = (
                        f"'{section.title()}' is mandatory for {standard_key} "
                        f"submissions but was not detected."
                    ),
                    suggestion = f"Add a dedicated '{section.title()}' section.",
                    category   = "structure",
                    location   = loc,
                ))
    return issues


def _check_section_order(parsed_document: dict) -> list[dict]:
    found: dict[str, int] = {}
    for page in parsed_document.get("pages", []):
        pn = page.get("page_number", 0)
        for line in page.get("heading_candidates", []):
            text = line.get("text", "").lower()
            for section in SECTION_ORDER:
                if any(a in text for a in SECTION_ALIASES.get(section, [section])):
                    rank = pn * 10_000 + int((line.get("bbox") or [0, 0, 0, 0])[1])
                    if section not in found or rank < found[section]:
                        found[section] = rank
                    break

    ordered = [s for s in SECTION_ORDER if s in found]
    for i in range(1, len(ordered)):
        if found[ordered[i]] < found[ordered[i - 1]]:
            return [_issue(
                issue_id   = "structure-order",
                severity   = "info",
                page       = None,
                message    = (
                    f"Section '{ordered[i].title()}' appears before "
                    f"'{ordered[i-1].title()}', breaking expected manuscript flow."
                ),
                suggestion = "Reorder sections to follow standard academic progression.",
                category   = "structure",
            )]
    return []


def _check_page_limit(
    parsed_document: dict, rules: dict, standard_key: str, strict: bool
) -> list[dict]:
    if not strict:
        return []
    limit = rules.get("page_limit_main")
    if limit is None:
        return []

    ref_page = None
    for page in parsed_document.get("pages", []):
        for line in page.get("heading_candidates", []):
            if "references" in line.get("text", "").strip().lower():
                ref_page = page.get("page_number")
                break
        if ref_page:
            break

    total      = parsed_document.get("page_count", 0)
    main_pages = total if ref_page is None else max(0, ref_page - 1)

    if main_pages > limit:
        return [_issue(
            issue_id   = "page-limit-main",
            severity   = "critical",
            page       = None,
            message    = (
                f"Main content is ~{main_pages} pages, "
                f"exceeding the {standard_key} limit of {limit} pages."
            ),
            suggestion = "Reduce main-body length or move content to supplementary material.",
        )]
    return []


# ═════════════════════════════════════════════════════════════════════════════
# 6.  ABSTRACT CHECKS
# ═════════════════════════════════════════════════════════════════════════════

def _extract_abstract(full_text: str) -> str:
    if not full_text:
        return ""
    lines = full_text.splitlines()
    start = next(
        (i + 1 for i, ln in enumerate(lines) if ln.strip().lower() == "abstract"),
        None,
    )
    if start is None:
        return ""

    stop = {"introduction", "1 introduction", "1. introduction", "keywords", "index terms"}
    abstract_lines: list[str] = []
    for line in lines[start:]:
        if line.strip().lower() in stop:
            break
        abstract_lines.append(line)
    return "\n".join(abstract_lines).strip()


def _check_abstract_rules(
    parsed_document: dict, rules: dict, standard_key: str
) -> list[dict]:
    issues: list[dict] = []
    abstract = _extract_abstract(parsed_document.get("full_text", ""))
    if not abstract:
        return issues

    if rules.get("abstract_single_paragraph"):
        paras = [b for b in re.split(r"\n\s*\n", abstract) if b.strip()]
        if len(paras) > 1:
            issues.append(_issue(
                issue_id   = "abstract-multi-paragraph",
                severity   = "warning",
                page       = None,
                message    = f"{standard_key} expects a single-paragraph abstract.",
                suggestion = "Merge the abstract into one compact paragraph.",
            ))

    citation_re = re.compile(
        r"\[\d+\]|\([A-Z][A-Za-z\-]+(?:\s+et\s+al\.)?,\s*\d{4}[a-z]?\)"
    )
    if citation_re.search(abstract):
        issues.append(_issue(
            issue_id   = "abstract-citation-detected",
            severity   = "info",
            page       = None,
            message    = "Citation-like pattern found in abstract.",
            suggestion = "Most venues discourage citations in the abstract.",
        ))
    return issues


# ═════════════════════════════════════════════════════════════════════════════
# 7.  BLIND REVIEW CHECK
# ═════════════════════════════════════════════════════════════════════════════

def _check_blind_review(
    parsed_document: dict, rules: dict, standard_key: str, review_mode: str | None
) -> list[dict]:
    mode = (review_mode or "").strip().lower()
    if not mode:
        mode = "blind" if rules.get("blind_review_default") else "camera_ready"
    if mode != "blind":
        return []

    if "acknowledg" in parsed_document.get("full_text", "").lower():
        return [_issue(
            issue_id   = "blind-review-acknowledgments",
            severity   = "info",
            page       = None,
            message    = "Acknowledgements section detected in a potential blind submission.",
            suggestion = "Remove or anonymise acknowledgements before blind submission.",
        )]
    return []


# ═════════════════════════════════════════════════════════════════════════════
# 8.  FIGURE / TABLE CHECKS
# ═════════════════════════════════════════════════════════════════════════════

def _normalise_table_num(raw: str) -> str:
    v = raw.strip().upper()
    return str(int(v)) if v.isdigit() else v


def _is_tabular_line(text: str) -> bool:
    tokens = text.split()
    nums   = len(re.findall(r"\b\d+(?:\.\d+)?\b", text))
    seps   = text.count("|") + text.count("&")
    gaps   = len(re.findall(r"\s{2,}", text))
    return len(tokens) >= 3 and (nums >= 2 or seps >= 2 or gaps >= 2)


def _check_figure_table_conventions(
    parsed_document: dict, standard_key: str, is_lenient: bool
) -> list[dict]:
    issues: list[dict] = []
    full_text = parsed_document.get("full_text", "")
    pages     = parsed_document.get("pages", [])

    figure_captions: list[dict] = []
    table_captions:  list[dict] = []

    for page in pages:
        pnum = page.get("page_number")
        for line in page.get("lines", []):
            text = (line.get("text") or "").strip()
            if not text:
                continue
            fm = FIGURE_CAPTION_RE.match(text)
            if fm:
                figure_captions.append({
                    "page": pnum, "label": fm.group(1),
                    "number": int(fm.group(2)), "bbox": line.get("bbox"), "text": text,
                })
                continue
            tm = TABLE_CAPTION_RE.match(text)
            if tm:
                table_captions.append({
                    "page": pnum, "number": _normalise_table_num(tm.group(1)),
                    "bbox": line.get("bbox"), "text": text,
                })

    fig_nums = [c["number"] for c in figure_captions]
    if fig_nums:
        uniq = sorted(set(fig_nums))
        if uniq != list(range(1, max(uniq) + 1)):
            issues.append(_issue(
                "figure-numbering-gap", "info", None,
                "Figure numbering appears non-sequential or has gaps.",
                "Number figures consecutively (1, 2, 3, …).",
            ))
        if len(set(fig_nums)) != len(fig_nums):
            issues.append(_issue(
                "figure-numbering-duplicate", "warning", None,
                "Duplicate figure numbers detected in captions.",
                "Each figure must have a unique caption number.",
            ))

    tbl_nums = [c["number"] for c in table_captions]
    if tbl_nums and len(set(tbl_nums)) != len(tbl_nums):
        issues.append(_issue(
            "table-numbering-duplicate", "warning", None,
            "Duplicate table numbers detected in captions.",
            "Each table must have a unique caption number.",
        ))

    fig_styles = {c["label"].lower() for c in figure_captions}
    if len(fig_styles) > 1:
        issues.append(_issue(
            "figure-label-mixed", "info", None,
            "Mixed figure caption labels ('Figure' and 'Fig.') detected.",
            "Use one style consistently throughout.",
        ))

    word_refs   = len(IN_TEXT_FIGURE_RE.findall(full_text))
    abbrev_refs = len(IN_TEXT_FIG_RE.findall(full_text))
    if word_refs > 0 and abbrev_refs > 0:
        issues.append(_issue(
            "figure-reference-mixed", "info", None,
            "Mixed in-text figure references ('Figure X' and 'Fig. X').",
            "Use a single in-text reference style.",
        ))

    if standard_key in {"IEEE", "CVPR", "ICCV"} and word_refs > abbrev_refs >= 2:
        issues.append(_issue(
            "figure-reference-ieee-style", "info", None,
            "IEEE-family venues prefer 'Fig. X' in running text.",
            "Replace 'Figure X' with 'Fig. X' for IEEE-style submissions.",
        ))

    in_text_figs = {
        int(n) for n in IN_TEXT_FIGURE_RE.findall(full_text)
    } | {int(n) for n in IN_TEXT_FIG_RE.findall(full_text)}
    cap_figs = {c["number"] for c in figure_captions}
    missing_figs = sorted(in_text_figs - cap_figs)
    if missing_figs:
        issues.append(_issue(
            "figure-reference-no-caption",
            "info" if is_lenient else "warning",
            None,
            f"In-text figure reference(s) with no matching caption: {missing_figs[:6]}",
            "Add the missing figure captions or fix the in-text references.",
        ))

    in_text_tbls = {_normalise_table_num(n) for n in IN_TEXT_TABLE_RE.findall(full_text)}
    cap_tbls = {c["number"] for c in table_captions}
    missing_tbls = sorted(in_text_tbls - cap_tbls)
    if missing_tbls:
        issues.append(_issue(
            "table-reference-no-caption",
            "info" if is_lenient else "warning",
            None,
            f"In-text table reference(s) with no matching caption: {missing_tbls[:6]}",
            "Add the missing table captions or fix the in-text references.",
        ))

    if re.search(
        r"\b(?:figure|fig\.|table)\s+\d+\s+(?:above|below)\b"
        r"|\b(?:above|below|following)\s+(?:figure|fig\.|table)\b",
        full_text, re.IGNORECASE,
    ):
        issues.append(_issue(
            "float-directional-reference", "info", None,
            "Directional float references ('Figure 2 above/below') detected.",
            "Use stable references like 'Figure 2' without positional words.",
        ))

    for tc in table_captions:
        page = next((p for p in pages if p.get("page_number") == tc["page"]), None)
        if not page:
            continue
        cap_y  = (tc.get("bbox") or [0, 0, 0, 0])[1]
        p_lines = page.get("lines", [])
        above_tab = any(
            _is_tabular_line((ln.get("text") or "").strip())
            for ln in p_lines
            if 0 < (cap_y - (ln.get("bbox") or [0, 0, 0, 0])[1]) <= 120
        )
        below_tab = any(
            _is_tabular_line((ln.get("text") or "").strip())
            for ln in p_lines
            if 0 < ((ln.get("bbox") or [0, 0, 0, 0])[1] - cap_y) <= 120
        )
        if above_tab and not below_tab:
            issues.append(_issue(
                issue_id   = f"table-caption-placement-{tc['page']}-{tc['number']}",
                severity   = "info",
                page       = tc["page"],
                message    = "Table caption may be placed below the table body.",
                suggestion = "Most venues require table captions above the table.",
                location   = {"bbox": tc.get("bbox")},
            ))

    return issues


# ═════════════════════════════════════════════════════════════════════════════
# 9.  UNLABELLED EQUATION CHECK
# ═════════════════════════════════════════════════════════════════════════════

def _check_unlabelled_equations(parsed_document: dict) -> list[dict]:
    full_text = parsed_document.get("full_text", "")
    if not full_text:
        return []
    labelled    = {int(m) for m in EQUATION_LABEL_RE.findall(full_text)}
    referenced  = {int(m) for m in IN_TEXT_EQ_RE.findall(full_text)}
    issues = []
    unreferenced = sorted(labelled - referenced)
    if unreferenced:
        issues.append(_issue(
            issue_id   = "equation-unreferenced",
            severity   = "info",
            page       = None,
            message    = f"Numbered equation(s) {unreferenced} are never cited in text.",
            suggestion = "Cite every numbered equation or remove the number.",
            category   = "content",
        ))
    phantom = sorted(referenced - labelled)
    if phantom:
        issues.append(_issue(
            issue_id   = "equation-missing-label",
            severity   = "warning",
            page       = None,
            message    = f"Equation number(s) {phantom} cited but no label '(N)' found.",
            suggestion = "Add the correct label or fix the citation number.",
            category   = "content",
        ))
    return issues


# ═════════════════════════════════════════════════════════════════════════════
# 10.  MAIN ORCHESTRATOR
# ═════════════════════════════════════════════════════════════════════════════

def check_formatting(
    parsed_document: dict,
    standard:    str,
    paper_type:  str | None = None,
    review_mode: str | None = None,
) -> list[dict]:
    standard_key = (standard or "IEEE").upper()
    rules        = get_standard(standard_key) or STANDARDS.get("IEEE", {})

    strict    = (paper_type or "").strip().lower() == "conference_submission"
    published = (review_mode or "").strip().lower() == "published" or bool(
        parsed_document.get("is_published_paper", False)
    )
    is_lenient = published

    pages          = parsed_document.get("pages", [])
    last_main_page = _last_main_content_page(parsed_document)

    geo_pages = pages[:1] if is_lenient else (
        [p for p in pages if p.get("page_number", 0) <= last_main_page] or pages
    )

    issues: list[dict] = []

    if strict:
        for page in geo_pages:
            issues.extend(_check_page_size(page, rules, standard_key, is_lenient))
            issues.extend(_check_margins(page, rules, is_lenient))
            issues.extend(_check_columns(page, rules, standard_key))

    if strict:
        issues.extend(_check_body_font(parsed_document, rules, standard_key, strict))
        issues.extend(_check_body_size(parsed_document, rules, standard_key, strict))

    issues.extend(_check_page_limit(parsed_document, rules, standard_key, strict))
    issues.extend(
        _check_required_sections(parsed_document, rules, standard_key, strict, published)
    )
    issues.extend(_check_section_order(parsed_document))
    issues.extend(_check_abstract_rules(parsed_document, rules, standard_key))
    issues.extend(_check_blind_review(parsed_document, rules, standard_key, review_mode))

    fig_table = _check_figure_table_conventions(parsed_document, standard_key, is_lenient)
    if published:
        for iss in fig_table:
            if iss["severity"] == "warning":
                iss["severity"] = "info"
    issues.extend(fig_table)

    issues.extend(_check_unlabelled_equations(parsed_document))

    issues.sort(key=lambda e: (e["page"] if e["page"] is not None else 9999, e["id"]))
    return issues


# ═════════════════════════════════════════════════════════════════════════════
# 11.  ONE-SHOT HELPER FOR FLASK ROUTES
# ═════════════════════════════════════════════════════════════════════════════

def run_format_check(
    pdf_path:    str,
    standard:    str       = "IEEE",
    paper_type:  str       = "conference_submission",
    review_mode: str | None = None,
) -> dict:
    # Use teammate's official extract_structure function [cite: 52, 97-98]
    elements = extract_structure(pdf_path)
    full_text = " ".join(el["text"] for el in elements)

    font_counter = Counter(el["font"]              for el in elements)
    size_counter = Counter(round(el["size"], 1)    for el in elements)
    page_count   = max((el["page"] for el in elements), default=1)

    pages_dict: dict[int, dict] = {}
    for el in elements:
        pn = el["page"]
        if pn not in pages_dict:
            pages_dict[pn] = {
                "page_number":        pn,
                "width":              el["page_width"],
                "height":             el["page_height"],
                "spans":              [],
                "lines":              [],
                "heading_candidates": [],
            }
        bbox = [el["x0"], el["y0"], el["x1"], el["y1"]]
        pages_dict[pn]["spans"].append({"bbox": bbox, "size": el["size"], "text": el["text"]})
        pages_dict[pn]["lines"].append({"text": el["text"], "bbox": bbox})
        # Promote bold spans as heading candidates for the structure checker [cite: 180, 242-243]
        if el["bold"] and len(el["text"]) < 60 and el["size"] >= 10:
            pages_dict[pn]["heading_candidates"].append({"text": el["text"], "bbox": bbox})

    parsed_document = {
        "full_text":     full_text,
        "dominant_font": font_counter.most_common(1)[0][0] if font_counter else "",
        "dominant_size": size_counter.most_common(1)[0][0] if size_counter else None,
        "page_count":    page_count,
        "pages":         list(pages_dict.values()),
    }

    issues = check_formatting(parsed_document, standard, paper_type, review_mode)

    return {
        "standard": standard,
        "elements": elements,
        "issues":   issues,
        "summary":  {
            "total":    len(issues),
            "critical": sum(1 for i in issues if i["severity"] == "critical"),
            "warning":  sum(1 for i in issues if i["severity"] == "warning"),
            "info":     sum(1 for i in issues if i["severity"] == "info"),
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
# 12.  QUICK CLI TEST
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    pdf  = sys.argv[1] if len(sys.argv) > 1 else "tests/sample_papers/sample_ieee.pdf"
    std  = sys.argv[2] if len(sys.argv) > 2 else "IEEE"
    mode = sys.argv[3] if len(sys.argv) > 3 else "conference_submission"

    try:
        result = run_format_check(pdf, standard=std, paper_type=mode)
        print(f"Summary: {result['summary']}")
        for iss in result["issues"]:
            print(f"[{iss['severity'].upper()}] {iss['message']}")
    except Exception as e:
        print(f"Error: {e}")