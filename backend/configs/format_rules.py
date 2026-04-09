# standards.py
# ─────────────────────────────────────────────────────────────────
# Formatting rules for major academic venues.
# All margins are in points (1 inch = 72 pt, 1 cm = 28.346 pt).
# ─────────────────────────────────────────────────────────────────

STANDARDS = {

    # ══════════════════════════════════════════════════════════════
    # IEEE — Conferences & Journals
    # ══════════════════════════════════════════════════════════════
    "IEEE": {
        "name": "IEEE Transactions / Conferences",
        "canonical_key": "IEEE",
        "page_width_pts": 595.28,           # A4
        "page_height_pts": 841.89,
        "allowed_page_sizes": [
            [595.28, 841.89],               # A4
            [612.0,  792.0 ],               # US Letter variant
        ],
        "citation_style": "IEEE_NUMERIC",   # [1], [2-4]
        "blind_review_default": False,
        "columns": 2,
        "body_font": "Times New Roman",
        "body_size": 10.0,
        "title_size": 24.0,
        "author_size": 11.0,
        "section_heading_size": 12.0,
        "subsection_heading_size": 11.0,
        "caption_size": 9.0,
        "margin_top":    54.0,              # ~0.75 inch
        "margin_bottom": 72.0,              # ~1.00 inch
        "margin_left":   45.0,              # ~0.625 inch
        "margin_right":  45.0,
        "tolerance_pts": 7.2,
        "tolerance_font_size": 0.5,
        "required_sections": ["abstract", "introduction", "conclusion", "references"],
        "strict_required_sections": [],
        "abstract_max_words": 250,
        "abstract_single_paragraph": False,
        "line_spacing": "single",
    },

    # ══════════════════════════════════════════════════════════════
    # Springer — LNCS / Journals
    # ══════════════════════════════════════════════════════════════
    "SPRINGER": {
        "name": "Springer Journals / LNCS",
        "canonical_key": "SPRINGER",
        "page_width_pts": 595.28,
        "page_height_pts": 841.89,
        "citation_style": "NUMERIC_OR_AUTHORYEAR",
        "blind_review_default": False,
        "columns": 1,
        "body_font": "Times",
        "body_size": 10.0,
        "title_size": 14.0,
        "author_size": 12.0,
        "section_heading_size": 14.0,
        "subsection_heading_size": 11.0,
        "caption_size": 10.0,
        "margin_top":    147.8,             # 5.2 cm
        "margin_bottom": 147.8,
        "margin_left":   124.7,             # 4.4 cm
        "margin_right":  124.7,
        "tolerance_pts": 7.2,
        "tolerance_font_size": 0.5,
        "required_sections": ["abstract", "introduction", "references"],
        "strict_required_sections": [],
        "abstract_max_words": 250,
        "abstract_single_paragraph": False,
        "line_spacing": 1.5,
    },

    # ══════════════════════════════════════════════════════════════
    # Elsevier — Journals
    # ══════════════════════════════════════════════════════════════
    "ELSEVIER": {
        "name": "Elsevier Journals",
        "canonical_key": "ELSEVIER",
        "page_width_pts": 595.28,
        "page_height_pts": 841.89,
        "citation_style": "NUMERIC_OR_AUTHORYEAR",
        "blind_review_default": False,
        "columns": 1,
        "body_font": "Times",
        "body_size": 11.0,
        "body_size_min": 10.0,
        "body_size_max": 12.0,
        "title_size": 16.0,
        "author_size": 12.0,
        "section_heading_size": 13.0,
        "subsection_heading_size": 12.0,
        "caption_size": 10.0,
        "margin_top":    72.0,              # 1.0 inch
        "margin_bottom": 72.0,
        "margin_left":   72.0,
        "margin_right":  72.0,
        "tolerance_pts": 7.2,
        "tolerance_font_size": 0.5,
        "required_sections": ["abstract", "keywords", "introduction", "conclusion", "references"],
        "strict_required_sections": [],
        "abstract_max_words": 250,
        "abstract_single_paragraph": False,
        "line_spacing": "single",
    },

    # ══════════════════════════════════════════════════════════════
    # ACL — NLP Conferences
    # ══════════════════════════════════════════════════════════════
    "ACL": {
        "name": "Association for Computational Linguistics",
        "canonical_key": "ACL",
        "page_width_pts": 595.276,          # A4
        "page_height_pts": 841.89,
        "page_limit_main": 8,
        "references_excluded_from_page_limit": True,
        "citation_style": "PARENTHETICAL_AUTHOR_YEAR",  # (Author, 2020)
        "blind_review_default": True,
        "columns": 2,
        "body_font": "Times Roman",
        "body_size": 11.0,
        "title_size": 15.0,
        "author_size": 12.0,
        "section_heading_size": 12.0,
        "subsection_heading_size": 11.0,
        "caption_size": 10.0,
        "footnote_size": 9.0,
        "margin_top_pts":    70.866,        # 2.5 cm
        "margin_bottom_pts": 70.866,
        "margin_left_pts":   70.866,
        "margin_right_pts":  70.866,
        "tolerance_pts": 3.0,
        "tolerance_font_size": 0.5,
        "required_sections": ["abstract", "introduction", "references"],
        "strict_required_sections": ["limitations"],
        "abstract_max_words": 200,
        "abstract_single_paragraph": False,
        "line_spacing": "single",
    },

    # ══════════════════════════════════════════════════════════════
    # CVPR — Computer Vision
    # ══════════════════════════════════════════════════════════════
    "CVPR": {
        "name": "IEEE/CVF Computer Vision and Pattern Recognition",
        "canonical_key": "CVPR",
        "page_width_pts": 612.0,            # US Letter
        "page_height_pts": 792.0,
        "allowed_page_sizes": [
            [612.0,  792.0 ],
            [595.28, 841.89],               # tolerate A4 exports
        ],
        "page_limit_main": 8,
        "references_excluded_from_page_limit": True,
        "citation_style": "IEEE_NUMERIC",
        "blind_review_default": True,
        "columns": 2,
        "body_font": "Times New Roman",
        "body_size": 10.0,
        "title_size": 14.0,
        "author_size": 12.0,
        "section_heading_size": 11.0,
        "subsection_heading_size": 10.0,
        "caption_size": 9.0,
        "margin_top":    72.0,
        "margin_bottom": 72.0,
        "margin_left":   72.0,
        "margin_right":  72.0,
        "tolerance_pts": 5.0,
        "tolerance_font_size": 0.5,
        "required_sections": ["abstract", "introduction", "conclusion", "references"],
        "strict_required_sections": [],
        "abstract_max_words": 300,
        "abstract_single_paragraph": False,
        "line_spacing": "single",
    },

    # ══════════════════════════════════════════════════════════════
    # NeurIPS — Machine Learning
    # ══════════════════════════════════════════════════════════════
    "NeurIPS": {
        "name": "Neural Information Processing Systems",
        "canonical_key": "NeurIPS",
        "page_width_pts": 612.0,
        "page_height_pts": 792.0,
        "allowed_page_sizes": [
            [612.0,  792.0 ],
            [595.28, 841.89],
        ],
        "page_limit_main": 9,
        "references_excluded_from_page_limit": True,
        "citation_style": "IEEE_NUMERIC_OR_AUTHORYEAR",
        "blind_review_default": True,
        "columns": 1,
        "body_font": "Times New Roman",
        "body_size": 11.0,
        "title_size": 16.0,
        "author_size": 12.0,
        "section_heading_size": 13.0,
        "subsection_heading_size": 12.0,
        "caption_size": 10.0,
        "margin_top":    72.0,
        "margin_bottom": 72.0,
        "margin_left":   72.0,
        "margin_right":  72.0,
        "tolerance_pts": 5.0,
        "tolerance_font_size": 0.5,
        "required_sections": ["abstract", "introduction", "conclusion", "references", "checklist"],
        "strict_required_sections": ["checklist"],
        "abstract_max_words": 300,
        "abstract_single_paragraph": True,
        "line_spacing": "single",
    },

    # ══════════════════════════════════════════════════════════════
    # ICML — Machine Learning
    # ══════════════════════════════════════════════════════════════
    "ICML": {
        "name": "International Conference on Machine Learning",
        "canonical_key": "ICML",
        "page_width_pts": 612.0,
        "page_height_pts": 792.0,
        "allowed_page_sizes": [
            [612.0,  792.0 ],
            [595.28, 841.89],
        ],
        "page_limit_main": 8,
        "references_excluded_from_page_limit": True,
        "citation_style": "IEEE_NUMERIC_OR_AUTHORYEAR",
        "blind_review_default": True,
        "columns": 1,
        "body_font": "Times",
        "body_size": 11.0,
        "title_size": 17.0,
        "author_size": 12.0,
        "section_heading_size": 13.0,
        "subsection_heading_size": 12.0,
        "caption_size": 10.0,
        "margin_top":    72.0,
        "margin_bottom": 72.0,
        "margin_left":   72.0,
        "margin_right":  72.0,
        "tolerance_pts": 5.0,
        "tolerance_font_size": 0.5,
        "required_sections": ["abstract", "introduction", "conclusion", "references"],
        "strict_required_sections": [],
        "abstract_max_words": 300,
        "abstract_single_paragraph": True,
        "line_spacing": "single",
    },

    # ══════════════════════════════════════════════════════════════
    # AAAI — Artificial Intelligence
    # ══════════════════════════════════════════════════════════════
    "AAAI": {
        "name": "Association for the Advancement of Artificial Intelligence",
        "canonical_key": "AAAI",
        "page_width_pts": 612.0,
        "page_height_pts": 792.0,
        "allowed_page_sizes": [
            [612.0,  792.0 ],
            [595.28, 841.89],
        ],
        "page_limit_main": 7,
        "references_excluded_from_page_limit": True,
        "citation_style": "IEEE_NUMERIC_OR_AUTHORYEAR",
        "blind_review_default": True,
        "columns": 2,
        "body_font": "Times",
        "body_size": 10.0,
        "title_size": 14.0,
        "author_size": 11.0,
        "section_heading_size": 11.0,
        "subsection_heading_size": 10.0,
        "caption_size": 9.0,
        "margin_top":    72.0,
        "margin_bottom": 72.0,
        "margin_left":   45.0,
        "margin_right":  45.0,
        "tolerance_pts": 5.0,
        "tolerance_font_size": 0.5,
        "required_sections": ["abstract", "introduction", "conclusion", "references", "checklist"],
        "strict_required_sections": ["checklist"],
        "abstract_max_words": 250,
        "abstract_single_paragraph": True,
        "line_spacing": "single",
    },
}


# ─────────────────────────────────────────────────────────────────
# Venue auto-detection signatures
# (used to guess the standard from PDF first-page text)
# ─────────────────────────────────────────────────────────────────
VENUE_SIGNATURES = {
    "IEEE": {
        "keywords": ["IEEE TRANSACTIONS", "IEEE CONFERENCE", "IEEE/ACM"],
        "min_matches": 1,
        "standards": ["IEEE"],
    },
    "CVPR": {
        "keywords": ["CVPR", "COMPUTER VISION AND PATTERN RECOGNITION", "CVF OPEN ACCESS"],
        "min_matches": 1,
        "standards": ["CVPR"],
    },
    "NeurIPS": {
        "keywords": ["NEURIPS", "NEURAL INFORMATION PROCESSING SYSTEMS",
                     "ADVANCES IN NEURAL INFORMATION PROCESSING SYSTEMS"],
        "min_matches": 1,
        "standards": ["NeurIPS"],
    },
    "ICML": {
        "keywords": ["INTERNATIONAL CONFERENCE ON MACHINE LEARNING",
                     "PROCEEDINGS OF MACHINE LEARNING RESEARCH", "PMLR", "ICML"],
        "min_matches": 1,
        "standards": ["ICML"],
    },
    "AAAI": {
        "keywords": ["AAAI", "ASSOCIATION FOR THE ADVANCEMENT OF ARTIFICIAL INTELLIGENCE"],
        "min_matches": 1,
        "standards": ["AAAI"],
    },
    "ACL": {
        "keywords": ["ASSOCIATION FOR COMPUTATIONAL LINGUISTICS", "ACL ANTHOLOGY"],
        "min_matches": 1,
        "standards": ["ACL"],
    },
    "SPRINGER": {
        "keywords": ["SPRINGER", "SPRINGER NATURE", "PUBLISHED BY SPRINGER"],
        "min_matches": 1,
        "standards": ["SPRINGER"],
    },
    "ELSEVIER": {
        "keywords": ["ELSEVIER", "SCIENCEDIRECT", "ARTICLE HISTORY"],
        "min_matches": 1,
        "standards": ["ELSEVIER"],
    },
}


# ─────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────

def get_standard(standard_name: str | None) -> dict | None:
    """
    Retrieve a standard dict by name (case-insensitive).

    Args:
        standard_name: e.g. 'IEEE', 'neurips', 'CVPR'

    Returns:
        The matching standard dict, or None if not found.
    """
    if not standard_name:
        return None

    # Direct lookup
    if standard_name in STANDARDS:
        return STANDARDS[standard_name]

    # Case-insensitive lookup
    normalized = standard_name.strip().upper()
    for key, value in STANDARDS.items():
        if key.upper() == normalized:
            return value

    # Common aliases
    aliases = {
        "NEURIPS": "NeurIPS",
        "ICCV":    "CVPR",    # ICCV follows same template family
        "3DV":     "CVPR",
    }
    alias_key = aliases.get(normalized)
    if alias_key and alias_key in STANDARDS:
        return STANDARDS[alias_key]

    return None


def get_all_standards() -> list[str]:
    """Return a list of all registered standard keys."""
    return list(STANDARDS.keys())


def detect_venue_from_text(first_page_text: str) -> tuple[str | None, float]:
    """
    Attempt to auto-detect publication venue from first-page PDF text.

    How it works (simple for beginners):
    - We uppercase the text and scan for known venue keywords.
    - The venue with the most keyword matches wins.
    - Confidence is how many of that venue's keywords were found (0.0–1.0).

    Args:
        first_page_text: Text from the first page of the PDF.

    Returns:
        (standard_name, confidence) e.g. ('IEEE', 0.67) or (None, 0.0)
    """
    if not first_page_text:
        return None, 0.0

    text_upper = first_page_text.upper()
    matches: dict[str, tuple[float, str]] = {}

    for venue_id, sig in VENUE_SIGNATURES.items():
        keywords      = sig["keywords"]
        min_matches   = int(sig.get("min_matches", 1))
        match_count   = sum(1 for kw in keywords if kw in text_upper)

        if match_count >= min_matches:
            ratio = match_count / max(1, len(keywords))
            matches[venue_id] = (ratio, sig["standards"][0])

    if not matches:
        return None, 0.0

    best_venue = max(matches, key=lambda k: matches[k][0])
    confidence = min(1.0, matches[best_venue][0])
    return matches[best_venue][1], confidence
