# """
# test_format.py
# ──────────────────────────────────────────────────────────────────────────────
# Unit tests for backend/modules/format_checker.py

# How to run
# ──────────
#     # From your project root (the folder that contains backend/)
#     python -m pytest backend/tests/test_format.py -v

#     # OR using plain unittest (no pytest needed)
#     python -m unittest backend/tests/test_format.py -v

#     # Run just one test class
#     python -m pytest backend/tests/test_format.py::TestMargins -v

#     # Run just one test method
#     python -m pytest backend/tests/test_format.py::TestAbstractRules::test_abstract_too_long -v

# What these tests do
# ────────────────────
# Instead of uploading a real PDF every time (slow!), we build small
# "fake" parsed_document dicts that look exactly like what pdf_ingestion.py
# produces.  We feed those directly to each check function and assert that
# the right issues (or no issues) come back.

# This is called "unit testing" — testing one small unit of code at a time.
# It is fast, repeatable, and tells you exactly which rule broke.

# Key idea:
#     real PDF  →  pdf_ingestion.py  →  parsed_document dict
#     We skip the first two steps and just hand-craft the dict ourselves.
# """

# import sys
# import os
# import unittest
# from unittest.mock import MagicMock

# # ── make sure Python can find our modules ─────────────────────────────────
# ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# sys.path.insert(0, ROOT)

# # ── mock fitz (PyMuPDF) so tests run without it installed ─────────────────
# # extract_structure() uses fitz, but all other functions only need plain dicts.
# # When you have fitz installed in your real environment this mock is ignored.
# if "fitz" not in sys.modules:
#     sys.modules["fitz"] = MagicMock()

# from backend.modules.format_checker import (
#     _check_page_size,
#     _check_margins,
#     _check_columns,
#     _check_body_font,
#     _check_body_size,
#     _check_required_sections,
#     _check_section_order,
#     _check_page_limit,
#     _check_abstract_rules,
#     _check_blind_review,
#     _check_figure_table_conventions,
#     _check_sentence_length,
#     _check_unlabelled_equations,
#     check_formatting,
# )
# from backend.configs.format_rules import get_standard


# # ══════════════════════════════════════════════════════════════════════════════
# # SHARED FIXTURES
# # Small helper functions that build fake dicts so we don't repeat ourselves.
# # ══════════════════════════════════════════════════════════════════════════════

# def _ieee():
#     """Return the IEEE rules dict."""
#     return get_standard("IEEE")


# def _make_page(
#     page_number: int = 1,
#     width: float = 595.28,
#     height: float = 841.89,
#     spans: list = None,
#     lines: list = None,
#     heading_candidates: list = None,
# ) -> dict:
#     """Build a minimal page dict that matches what pdf_ingestion.py produces."""
#     return {
#         "page_number":        page_number,
#         "width":              width,
#         "height":             height,
#         "spans":              spans or [],
#         "lines":              lines or [],
#         "heading_candidates": heading_candidates or [],
#     }


# def _make_span(x0=50, y0=100, x1=300, y1=115, size=10.0, text="Sample body text.") -> dict:
#     """A single text span — the smallest unit extracted from a PDF."""
#     return {"bbox": [x0, y0, x1, y1], "size": size, "text": text}


# def _make_doc(
#     full_text: str = "",
#     dominant_font: str = "TimesNewRomanPSMT",
#     dominant_size: float = 10.0,
#     page_count: int = 5,
#     pages: list = None,
# ) -> dict:
#     """Build a minimal parsed_document dict."""
#     return {
#         "full_text":     full_text,
#         "dominant_font": dominant_font,
#         "dominant_size": dominant_size,
#         "page_count":    page_count,
#         "pages":         pages or [],
#     }


# def _ids(issues: list) -> list:
#     """Extract just the issue IDs from a list of issues — handy for assertions."""
#     return [i["id"] for i in issues]


# def _severities(issues: list) -> list:
#     return [i["severity"] for i in issues]


# # ══════════════════════════════════════════════════════════════════════════════
# # TEST CLASSES
# # Each class tests one check function in isolation.
# # ══════════════════════════════════════════════════════════════════════════════


# class TestPageSize(unittest.TestCase):
#     """Tests for _check_page_size()"""

#     def setUp(self):
#         self.rules = _ieee()

#     def test_correct_a4_size_passes(self):
#         """An A4 page should produce no issues."""
#         page = _make_page(width=595.28, height=841.89)
#         issues = _check_page_size(page, self.rules, "IEEE", is_lenient=False)
#         self.assertEqual(issues, [], "A4 page should pass IEEE size check")

#     def test_us_letter_in_allowed_list_passes(self):
#         """US Letter is in IEEE's allowed_page_sizes list and should pass."""
#         page = _make_page(width=612.0, height=792.0)
#         issues = _check_page_size(page, self.rules, "IEEE", is_lenient=False)
#         self.assertEqual(issues, [], "US Letter should be accepted for IEEE")

#     def test_wrong_size_produces_warning(self):
#         """A clearly wrong page size should flag a warning."""
#         page = _make_page(width=400.0, height=600.0)   # some random size
#         issues = _check_page_size(page, self.rules, "IEEE", is_lenient=False)
#         self.assertTrue(len(issues) > 0, "Wrong page size should be flagged")
#         self.assertIn("page-size-1", _ids(issues))
#         self.assertEqual(issues[0]["severity"], "warning")

#     def test_wrong_size_is_info_when_lenient(self):
#         """For published papers (lenient mode), page-size issues are downgraded to info."""
#         page = _make_page(width=400.0, height=600.0)
#         issues = _check_page_size(page, self.rules, "IEEE", is_lenient=True)
#         # Either no issues (within doubled tolerance) or severity is 'info'
#         for iss in issues:
#             self.assertEqual(iss["severity"], "info",
#                              "Published-paper size issues should be info, not warning")

#     def test_tolerance_boundary(self):
#         """A page within the 7.2 pt tolerance should not be flagged."""
#         # 595.28 + 6.0 = 601.28 — still within 7.2 pt tolerance
#         page = _make_page(width=601.0, height=841.89)
#         issues = _check_page_size(page, self.rules, "IEEE", is_lenient=False)
#         self.assertEqual(issues, [], "Page within tolerance should not be flagged")


# class TestMargins(unittest.TestCase):
#     """Tests for _check_margins()"""

#     def setUp(self):
#         self.rules = _ieee()
#         # IEEE left margin = 45 pt.  So text starting at x0=50 is fine.
#         # Page is 595.28 wide.  Text ending at x1=545 → right margin = 50.28 — fine.

#     def _good_span(self):
#         """A span comfortably within IEEE margins."""
#         return _make_span(x0=50, y0=100, x1=545, y1=115, size=10.0)

#     def _page_with_spans(self, spans):
#         return _make_page(
#             width=595.28, height=841.89,
#             spans=spans,
#         )

#     def test_correct_margins_pass(self):
#         # IEEE margins: top=54, bottom=72, left=45, right=45. Tolerance=7.2 pt.
#         # x0=50  → left margin=50,   delta from 45=5.0  < 7.2 ✓
#         # x1=545 → right margin=50.28, delta from 45=5.28 < 7.2 ✓
#         # y0=58  → top margin=58,    delta from 54=4.0  < 7.2 ✓
#         # y1=765 → bottom margin=76.89, delta from 72=4.89 < 7.2 ✓
#         good_span = _make_span(x0=50, y0=58, x1=545, y1=765, size=10.0)
#         page = self._page_with_spans([good_span])
#         issues = _check_margins(page, self.rules, is_lenient=False)
#         self.assertEqual(issues, [], "Text within margins should pass")

#     def test_left_margin_violation(self):
#         """Text starting at x0=10 violates the 45 pt left margin."""
#         bad_span = _make_span(x0=10, y0=100, x1=545, y1=115, size=10.0)
#         page = self._page_with_spans([bad_span])
#         issues = _check_margins(page, self.rules, is_lenient=False)
#         ids = _ids(issues)
#         self.assertTrue(
#             any("margin-left" in i for i in ids),
#             f"Left margin violation not detected. Got: {ids}"
#         )

#     def test_right_margin_violation(self):
#         """Text ending at x1=590 on a 595.28-wide page → right margin ≈ 5 pt, below 45 pt."""
#         bad_span = _make_span(x0=50, y0=100, x1=590, y1=115, size=10.0)
#         page = self._page_with_spans([bad_span])
#         issues = _check_margins(page, self.rules, is_lenient=False)
#         ids = _ids(issues)
#         self.assertTrue(
#             any("margin-right" in i for i in ids),
#             f"Right margin violation not detected. Got: {ids}"
#         )

#     def test_empty_page_returns_no_issues(self):
#         """A page with no spans should not crash — just return []."""
#         page = _make_page(width=595.28, height=841.89, spans=[])
#         issues = _check_margins(page, self.rules, is_lenient=False)
#         self.assertEqual(issues, [])

#     def test_header_spans_are_ignored(self):
#         """
#         A span in the top 6% of the page (y0 < 841.89*0.06 ≈ 50.5 pt)
#         should be filtered out as a header and not trigger a margin violation.
#         """
#         header_span = _make_span(x0=5, y0=20, x1=590, y1=35, size=10.0,
#                                  text="Page header that is very wide")
#         body_span   = self._good_span()
#         page = self._page_with_spans([header_span, body_span])
#         issues = _check_margins(page, self.rules, is_lenient=False)
#         # The header's x0=5 would violate left margin, but should be ignored
#         ids = _ids(issues)
#         self.assertFalse(
#             any("margin-left" in i for i in ids),
#             "Header spans should be excluded from margin checks"
#         )


# class TestColumns(unittest.TestCase):
#     """Tests for _check_columns()"""

#     def setUp(self):
#         self.rules = _ieee()   # IEEE requires 2 columns

#     def _make_two_col_lines(self, page_width=595.28):
#         """Generate fake lines distributed in left and right columns."""
#         mid = page_width / 2
#         lines = []
#         # 10 lines in left column
#         for i in range(10):
#             lines.append({"bbox": [50, 100 + i*20, mid - 10, 115 + i*20], "text": "Left col"})
#         # 10 lines in right column
#         for i in range(10):
#             lines.append({"bbox": [mid + 10, 100 + i*20, page_width - 50, 115 + i*20],
#                           "text": "Right col"})
#         return lines

#     def test_two_column_layout_passes(self):
#         lines = self._make_two_col_lines()
#         page  = _make_page(width=595.28, height=841.89, lines=lines)
#         issues = _check_columns(page, self.rules, "IEEE")
#         self.assertEqual(issues, [], "Proper two-column layout should pass")

#     def test_single_column_in_two_col_standard_flagged(self):
#         """All lines span the full width → looks single-column → should flag."""
#         full_width_lines = [
#             {"bbox": [50, 100 + i*20, 545, 115 + i*20], "text": "Full width line"}
#             for i in range(12)
#         ]
#         page   = _make_page(width=595.28, height=841.89, lines=full_width_lines)
#         issues = _check_columns(page, self.rules, "IEEE")
#         self.assertTrue(len(issues) > 0, "Single-column in 2-col standard should be flagged")
#         self.assertIn(f"columns-{page['page_number']}", _ids(issues))

#     def test_single_col_standard_never_flagged(self):
#         """Springer is single-column — no column check should run at all."""
#         rules = get_standard("SPRINGER")
#         lines = [{"bbox": [50, 100 + i*20, 545, 115 + i*20], "text": "Body"} for i in range(12)]
#         page  = _make_page(lines=lines)
#         issues = _check_columns(page, rules, "SPRINGER")
#         self.assertEqual(issues, [], "Single-col standard should never flag column issues")

#     def test_too_few_lines_skipped(self):
#         """Fewer than 8 lines — not enough data to determine column layout."""
#         lines = [{"bbox": [50, 100], "text": "x"}] * 5
#         page  = _make_page(lines=lines)
#         issues = _check_columns(page, self.rules, "IEEE")
#         self.assertEqual(issues, [])


# class TestBodyFont(unittest.TestCase):
#     """Tests for _check_body_font()"""

#     def setUp(self):
#         self.rules = _ieee()   # expects Times New Roman

#     def test_correct_font_passes(self):
#         doc = _make_doc(dominant_font="TimesNewRomanPSMT")
#         issues = _check_body_font(doc, self.rules, "IEEE", strict=True)
#         self.assertEqual(issues, [], "Times New Roman variant should pass")

#     def test_wrong_font_flagged(self):
#         doc = _make_doc(dominant_font="Arial")
#         issues = _check_body_font(doc, self.rules, "IEEE", strict=True)
#         self.assertTrue(len(issues) > 0, "Arial should be flagged for IEEE")
#         self.assertEqual(issues[0]["id"], "font-body-mismatch")

#     def test_wrong_font_is_warning_in_strict(self):
#         doc = _make_doc(dominant_font="Helvetica")
#         issues = _check_body_font(doc, self.rules, "IEEE", strict=True)
#         self.assertEqual(issues[0]["severity"], "warning")

#     def test_wrong_font_is_info_in_lenient(self):
#         doc = _make_doc(dominant_font="Helvetica")
#         issues = _check_body_font(doc, self.rules, "IEEE", strict=False)
#         self.assertEqual(issues[0]["severity"], "info")

#     def test_missing_font_info_skipped(self):
#         """If dominant_font is empty, no check should run."""
#         doc = _make_doc(dominant_font="")
#         issues = _check_body_font(doc, self.rules, "IEEE", strict=True)
#         self.assertEqual(issues, [])


# class TestBodySize(unittest.TestCase):
#     """Tests for _check_body_size()"""

#     def setUp(self):
#         self.rules = _ieee()   # expects 10.0 pt

#     def test_correct_size_passes(self):
#         doc = _make_doc(dominant_size=10.0)
#         self.assertEqual(_check_body_size(doc, self.rules, "IEEE", strict=True), [])

#     def test_size_within_tolerance_passes(self):
#         doc = _make_doc(dominant_size=10.4)  # within 0.5 pt tolerance
#         self.assertEqual(_check_body_size(doc, self.rules, "IEEE", strict=True), [])

#     def test_size_outside_tolerance_flagged(self):
#         doc = _make_doc(dominant_size=12.0)  # 2 pt off
#         issues = _check_body_size(doc, self.rules, "IEEE", strict=True)
#         self.assertTrue(len(issues) > 0)
#         self.assertEqual(issues[0]["id"], "font-size-body")

#     def test_elsevier_range_accepted(self):
#         """Elsevier accepts 10–12 pt; 11 pt should pass."""
#         rules = get_standard("ELSEVIER")
#         doc   = _make_doc(dominant_size=11.0)
#         self.assertEqual(_check_body_size(doc, rules, "ELSEVIER", strict=True), [])

#     def test_none_size_skipped(self):
#         doc = _make_doc(dominant_size=None)
#         self.assertEqual(_check_body_size(doc, self.rules, "IEEE", strict=True), [])


# class TestRequiredSections(unittest.TestCase):
#     """Tests for _check_required_sections()"""

#     def setUp(self):
#         self.rules = _ieee()

#     def _doc(self, text):
#         return _make_doc(full_text=text)

#     def test_all_sections_present_passes(self):
#         text = "Abstract\nsome abstract text\nIntroduction\nbody\nConclusion\nfinal\nReferences\n[1]"
#         doc  = self._doc(text)
#         issues = _check_required_sections(doc, self.rules, "IEEE",
#                                           strict=False, published=False)
#         self.assertEqual(issues, [])

#     def test_missing_abstract_flagged(self):
#         text = "Introduction\nbody\nConclusion\nfinal\nReferences\n[1]"
#         doc  = self._doc(text)
#         issues = _check_required_sections(doc, self.rules, "IEEE",
#                                           strict=False, published=False)
#         ids = _ids(issues)
#         self.assertIn("structure-missing-abstract", ids)

#     def test_missing_references_flagged(self):
#         text = "Abstract\nintro\nIntroduction\nbody\nConclusion\nfinal"
#         doc  = self._doc(text)
#         issues = _check_required_sections(doc, self.rules, "IEEE",
#                                           strict=False, published=False)
#         self.assertIn("structure-missing-references", _ids(issues))

#     def test_published_paper_missing_section_is_info(self):
#         """For published papers, missing sections are downgraded to info."""
#         text = "Introduction\nbody\nReferences\n[1]"  # no abstract
#         doc  = self._doc(text)
#         issues = _check_required_sections(doc, self.rules, "IEEE",
#                                           strict=False, published=True)
#         for iss in issues:
#             self.assertEqual(iss["severity"], "info",
#                              "Published paper missing section should be info")

#     def test_neurips_requires_checklist(self):
#         """NeurIPS strictly requires a 'checklist' section in conference submissions."""
#         rules = get_standard("NeurIPS")
#         text  = "Abstract\nIntroduction\nConclusion\nReferences"  # no checklist
#         doc   = self._doc(text)
#         issues = _check_required_sections(doc, rules, "NeurIPS",
#                                           strict=True, published=False)
#         ids = _ids(issues)
#         self.assertIn("structure-required-checklist", ids,
#                       "NeurIPS should critically require checklist section")
#         checklist_issue = next(i for i in issues if i["id"] == "structure-required-checklist")
#         self.assertEqual(checklist_issue["severity"], "critical")

#     def test_acl_requires_limitations(self):
#         """ACL strictly requires a 'limitations' section."""
#         rules = get_standard("ACL")
#         text  = "Abstract\nIntroduction\nConclusion\nReferences"  # no limitations
#         doc   = self._doc(text)
#         issues = _check_required_sections(doc, rules, "ACL",
#                                           strict=True, published=False)
#         ids = _ids(issues)
#         self.assertIn("structure-required-limitations", ids)


# class TestSectionOrder(unittest.TestCase):
#     """Tests for _check_section_order()"""

#     def _make_heading(self, text, page_num, y=100):
#         return {"text": text, "bbox": [50, y, 200, y + 15]}

#     def _doc_with_headings(self, headings_by_page):
#         """
#         headings_by_page: list of (page_num, heading_text, y_position)
#         """
#         pages = []
#         for page_num, heading_text, y in headings_by_page:
#             pages.append(_make_page(
#                 page_number=page_num,
#                 heading_candidates=[self._make_heading(heading_text, page_num, y)],
#             ))
#         return _make_doc(pages=pages)

#     def test_correct_order_passes(self):
#         doc = self._doc_with_headings([
#             (1, "Abstract",     100),
#             (2, "Introduction", 100),
#             (3, "Method",       100),
#             (4, "Results",      100),
#             (5, "Conclusion",   100),
#             (6, "References",   100),
#         ])
#         issues = _check_section_order(doc)
#         self.assertEqual(issues, [], "Correct section order should pass")

#     def test_conclusion_before_results_flagged(self):
#         doc = self._doc_with_headings([
#             (1, "Abstract",     100),
#             (2, "Introduction", 100),
#             (3, "Conclusion",   100),   # comes before Results — wrong
#             (4, "Results",      100),
#             (5, "References",   100),
#         ])
#         issues = _check_section_order(doc)
#         self.assertTrue(len(issues) > 0, "Out-of-order sections should be flagged")
#         self.assertEqual(issues[0]["id"], "structure-order")
#         self.assertEqual(issues[0]["severity"], "info")

#     def test_single_section_never_flagged(self):
#         doc = self._doc_with_headings([(1, "References", 100)])
#         issues = _check_section_order(doc)
#         self.assertEqual(issues, [])


# class TestPageLimit(unittest.TestCase):
#     """Tests for _check_page_limit()"""

#     def setUp(self):
#         self.cvpr = get_standard("CVPR")   # limit = 8 pages

#     def _doc(self, page_count, ref_page=None):
#         pages = []
#         if ref_page:
#             pages.append(_make_page(
#                 page_number=ref_page,
#                 heading_candidates=[{"text": "References", "bbox": [50, 100, 200, 115]}],
#             ))
#         return _make_doc(page_count=page_count, pages=pages)

#     def test_within_limit_passes(self):
#         doc = self._doc(page_count=8, ref_page=9)   # 8 main pages
#         issues = _check_page_limit(doc, self.cvpr, "CVPR", strict=True)
#         self.assertEqual(issues, [])

#     def test_over_limit_flagged(self):
#         doc = self._doc(page_count=12, ref_page=11)  # 10 main pages > 8
#         issues = _check_page_limit(doc, self.cvpr, "CVPR", strict=True)
#         self.assertTrue(len(issues) > 0)
#         self.assertEqual(issues[0]["id"], "page-limit-main")
#         self.assertEqual(issues[0]["severity"], "critical")

#     def test_lenient_mode_skips_check(self):
#         """Page limit is only checked in strict (conference submission) mode."""
#         doc = self._doc(page_count=20, ref_page=19)
#         issues = _check_page_limit(doc, self.cvpr, "CVPR", strict=False)
#         self.assertEqual(issues, [], "Page limit should not be checked in lenient mode")

#     def test_standard_without_limit_passes(self):
#         """SPRINGER has no page_limit_main — should never flag."""
#         rules = get_standard("SPRINGER")
#         doc   = self._doc(page_count=50)
#         issues = _check_page_limit(doc, rules, "SPRINGER", strict=True)
#         self.assertEqual(issues, [])


# class TestAbstractRules(unittest.TestCase):
#     """Tests for _check_abstract_rules()"""

#     def _doc(self, abstract_body):
#         full_text = f"Abstract\n{abstract_body}\nIntroduction\nbody"
#         return _make_doc(full_text=full_text)

#     def test_short_abstract_passes(self):
#         doc = self._doc("This paper presents a concise method. " * 5)
#         rules = _ieee()
#         issues = _check_abstract_rules(doc, rules, "IEEE")
#         ids = _ids(issues)
#         self.assertNotIn("abstract-word-count", ids)

#     def test_long_abstract_flagged(self):
#         # IEEE limit = 250 words; generate 280 words
#         doc = self._doc(("word " * 280).strip())
#         rules = _ieee()
#         issues = _check_abstract_rules(doc, rules, "IEEE")
#         self.assertIn("abstract-word-count", _ids(issues))

#     def test_multi_paragraph_abstract_flagged_for_neurips(self):
#         """NeurIPS requires a single paragraph abstract."""
#         doc   = self._doc("First paragraph text.\n\nSecond paragraph text.")
#         rules = get_standard("NeurIPS")
#         issues = _check_abstract_rules(doc, rules, "NeurIPS")
#         self.assertIn("abstract-multi-paragraph", _ids(issues))

#     def test_multi_paragraph_ok_for_ieee(self):
#         """IEEE does not require single-paragraph abstract."""
#         doc   = self._doc("First paragraph.\n\nSecond paragraph.")
#         rules = _ieee()
#         issues = _check_abstract_rules(doc, rules, "IEEE")
#         self.assertNotIn("abstract-multi-paragraph", _ids(issues))

#     def test_citation_in_abstract_flagged(self):
#         doc = self._doc("We build on [1] prior work and show results.")
#         rules = _ieee()
#         issues = _check_abstract_rules(doc, rules, "IEEE")
#         self.assertIn("abstract-citation-detected", _ids(issues))

#     def test_author_year_citation_in_abstract_flagged(self):
#         doc = self._doc("Building on (Smith et al., 2020) we propose a new method.")
#         rules = _ieee()
#         issues = _check_abstract_rules(doc, rules, "IEEE")
#         self.assertIn("abstract-citation-detected", _ids(issues))

#     def test_no_abstract_heading_returns_empty(self):
#         """If there is no 'Abstract' heading in the text, the check is skipped."""
#         doc = _make_doc(full_text="Introduction\nbody\nConclusion\nend")
#         issues = _check_abstract_rules(doc, _ieee(), "IEEE")
#         self.assertEqual(issues, [])


# class TestBlindReview(unittest.TestCase):
#     """Tests for _check_blind_review()"""

#     def setUp(self):
#         # ACL has blind_review_default = True
#         self.rules = get_standard("ACL")

#     def test_no_acknowledgements_passes(self):
#         doc = _make_doc(full_text="Abstract\nIntro\nConclusion\nReferences")
#         issues = _check_blind_review(doc, self.rules, "ACL", review_mode="blind")
#         self.assertEqual(issues, [])

#     def test_acknowledgements_in_blind_submission_flagged(self):
#         doc = _make_doc(full_text="Abstract\nConclusion\nAcknowledgements\nThanks to...")
#         issues = _check_blind_review(doc, self.rules, "ACL", review_mode="blind")
#         self.assertIn("blind-review-acknowledgments", _ids(issues))

#     def test_acknowledgements_in_camera_ready_not_flagged(self):
#         doc = _make_doc(full_text="Abstract\nAcknowledgements\nThanks to XYZ grant.")
#         issues = _check_blind_review(doc, self.rules, "ACL", review_mode="camera_ready")
#         self.assertEqual(issues, [])

#     def test_ieee_not_blind_by_default(self):
#         """IEEE does not require blind review — acknowledgements should not be flagged."""
#         rules = _ieee()
#         doc   = _make_doc(full_text="Acknowledgements\nThis work was funded by...")
#         issues = _check_blind_review(doc, rules, "IEEE", review_mode=None)
#         self.assertEqual(issues, [],
#                          "IEEE is not blind-review by default; ack should not be flagged")


# class TestFigureTableConventions(unittest.TestCase):
#     """Tests for _check_figure_table_conventions()"""

#     def _doc_with_text(self, full_text, lines_per_page=None):
#         pages = [_make_page(
#             lines=lines_per_page or [],
#             heading_candidates=[],
#         )]
#         return _make_doc(full_text=full_text, pages=pages)

#     def test_no_figures_no_issues(self):
#         doc = self._doc_with_text("We present our method in detail.")
#         issues = _check_figure_table_conventions(doc, "IEEE", is_lenient=False)
#         self.assertEqual(issues, [])

#     def test_duplicate_figure_numbers_flagged(self):
#         lines = [
#             {"text": "Figure 1. First plot.", "bbox": [50, 100, 300, 115]},
#             {"text": "Figure 1. Second plot.", "bbox": [50, 200, 300, 215]},  # duplicate!
#         ]
#         full_text = "See Figure 1 for results. Also Figure 1 shows more."
#         doc = _make_doc(full_text=full_text, pages=[_make_page(lines=lines)])
#         issues = _check_figure_table_conventions(doc, "IEEE", is_lenient=False)
#         self.assertIn("figure-numbering-duplicate", _ids(issues))

#     def test_non_sequential_figure_numbers_flagged(self):
#         lines = [
#             {"text": "Figure 1. First.", "bbox": [50, 100, 300, 115]},
#             {"text": "Figure 3. Third.", "bbox": [50, 200, 300, 215]},  # gap at 2
#         ]
#         doc = _make_doc(
#             full_text="See Figure 1 and Figure 3.",
#             pages=[_make_page(lines=lines)],
#         )
#         issues = _check_figure_table_conventions(doc, "IEEE", is_lenient=False)
#         self.assertIn("figure-numbering-gap", _ids(issues))

#     def test_missing_figure_caption_flagged(self):
#         """Text references Figure 2 but there is no 'Figure 2.' caption line."""
#         lines = [
#             {"text": "Figure 1. Only figure.", "bbox": [50, 100, 300, 115]},
#         ]
#         full_text = "See Figure 1 and also Figure 2 for comparison."
#         doc = _make_doc(full_text=full_text, pages=[_make_page(lines=lines)])
#         issues = _check_figure_table_conventions(doc, "IEEE", is_lenient=False)
#         self.assertIn("figure-reference-no-caption", _ids(issues))

#     def test_mixed_figure_labels_flagged(self):
#         lines = [
#             {"text": "Figure 1. First plot.",   "bbox": [50, 100, 300, 115]},
#             {"text": "Fig. 2. Second plot.",     "bbox": [50, 200, 300, 215]},
#         ]
#         doc = _make_doc(
#             full_text="See Figure 1 and Fig. 2.",
#             pages=[_make_page(lines=lines)],
#         )
#         issues = _check_figure_table_conventions(doc, "IEEE", is_lenient=False)
#         self.assertIn("figure-label-mixed", _ids(issues))

#     def test_directional_reference_flagged(self):
#         doc = self._doc_with_text("As shown in Figure 2 above, the results confirm...")
#         issues = _check_figure_table_conventions(doc, "IEEE", is_lenient=False)
#         self.assertIn("float-directional-reference", _ids(issues))

#     def test_clean_document_passes(self):
#         lines = [
#             {"text": "Figure 1. The result.",   "bbox": [50, 100, 300, 115]},
#             {"text": "Figure 2. More results.", "bbox": [50, 300, 300, 315]},
#         ]
#         full_text = "See Figure 1 for the main result and Figure 2 for ablations."
#         doc = _make_doc(full_text=full_text, pages=[_make_page(lines=lines)])
#         issues = _check_figure_table_conventions(doc, "IEEE", is_lenient=False)
#         # Should be clean — no duplicates, no gaps, no mixed labels, no missing captions
#         flagged_ids = _ids(issues)
#         for bad_id in ["figure-numbering-duplicate", "figure-numbering-gap",
#                        "figure-reference-no-caption", "figure-label-mixed"]:
#             self.assertNotIn(bad_id, flagged_ids, f"{bad_id} should not be flagged")


# class TestSentenceLength(unittest.TestCase):
#     """Tests for _check_sentence_length()  — NEW extra check #1"""

#     def test_short_sentences_pass(self):
#         text = "We propose a new method. It works well. Results are good."
#         doc  = _make_doc(full_text=text)
#         issues = _check_sentence_length(doc)
#         self.assertEqual(issues, [], "Short sentences should not be flagged")

#     def test_long_sentence_flagged(self):
#         # Build a single sentence that is clearly over 60 words.
#         # Must end with a period so re.split picks it up correctly.
#         words = " ".join(["word"] * 70)
#         doc  = _make_doc(full_text=words + ".")
#         issues = _check_sentence_length(doc)
#         self.assertTrue(len(issues) > 0, "70-word sentence should be flagged")
#         self.assertTrue(all(i["category"] == "readability" for i in issues))
#         self.assertTrue(all(i["severity"] == "info" for i in issues))

#     def test_at_most_5_examples_reported(self):
#         """Even with 10 long sentences, we report at most 5."""
#         long_sent = ("word " * 70).strip() + ". "
#         doc = _make_doc(full_text=long_sent * 10)
#         issues = _check_sentence_length(doc)
#         self.assertLessEqual(len(issues), 5,
#                              "At most 5 long-sentence issues should be reported")

#     def test_empty_text_returns_no_issues(self):
#         doc = _make_doc(full_text="")
#         self.assertEqual(_check_sentence_length(doc), [])

#     def test_reference_list_not_flagged(self):
#         """
#         Reference entries can be very long strings but should be ignored
#         (we skip sentences over 500 words — these are reference dumps).
#         """
#         ref_dump = "word " * 600   # 600 words — treated as a reference block
#         doc = _make_doc(full_text=ref_dump)
#         issues = _check_sentence_length(doc)
#         self.assertEqual(issues, [], "600-word reference dump should be ignored")


# class TestUnlabelledEquations(unittest.TestCase):
#     """Tests for _check_unlabelled_equations()  — NEW extra check #2"""

#     def test_labelled_and_referenced_passes(self):
#         text = "We minimise the loss function\n  L = sum(errors)  (1)\nas shown in Eq. (1)."
#         doc  = _make_doc(full_text=text)
#         issues = _check_unlabelled_equations(doc)
#         self.assertEqual(issues, [], "Labelled and referenced equation should pass")

#     def test_labelled_but_not_referenced_flagged(self):
#         text = "We define the function\n  f(x) = x^2  (1)\nbut never mention it again."
#         doc  = _make_doc(full_text=text)
#         issues = _check_unlabelled_equations(doc)
#         self.assertIn("equation-unreferenced", _ids(issues))

#     def test_referenced_but_not_labelled_flagged(self):
#         text = "As shown in Eq. (3), the result holds. But there is no equation (3) label."
#         doc  = _make_doc(full_text=text)
#         issues = _check_unlabelled_equations(doc)
#         self.assertIn("equation-missing-label", _ids(issues))
#         eq_issue = next(i for i in issues if i["id"] == "equation-missing-label")
#         self.assertEqual(eq_issue["severity"], "warning")

#     def test_no_equations_returns_empty(self):
#         doc = _make_doc(full_text="No equations here. Just words.")
#         self.assertEqual(_check_unlabelled_equations(doc), [])

#     def test_empty_text_returns_empty(self):
#         doc = _make_doc(full_text="")
#         self.assertEqual(_check_unlabelled_equations(doc), [])


# class TestCheckFormattingOrchestrator(unittest.TestCase):
#     """
#     Integration-level tests for check_formatting() — the main function.
#     These test that the orchestrator calls the right checks and respects
#     the strict/published/review_mode flags.
#     """

#     def _full_doc(self):
#         """A complete parsed_document with all required sections present."""
#         text = (
#             "Abstract\n"
#             "This paper presents a new method for doing things better.\n"
#             "Introduction\n"
#             "We introduce our approach.\n"
#             "Method\n"
#             "We do the following.\n"
#             "Results\n"
#             "We achieve 95% accuracy.\n"
#             "Conclusion\n"
#             "We conclude the work.\n"
#             "References\n"
#             "[1] Smith et al. 2020.\n"
#         )
#         heading_candidates = [
#             {"text": "Abstract",     "bbox": [50,  50, 200,  65]},
#             {"text": "Introduction", "bbox": [50, 150, 200, 165]},
#             {"text": "Method",       "bbox": [50, 250, 200, 265]},
#             {"text": "Results",      "bbox": [50, 350, 200, 365]},
#             {"text": "Conclusion",   "bbox": [50, 450, 200, 465]},
#             {"text": "References",   "bbox": [50, 550, 200, 565]},
#         ]
#         spans = [
#             _make_span(x0=50, y0=100, x1=545, y1=115, size=10.0,
#                        text="Sample body text that is long enough.")
#         ]
#         page = _make_page(
#             width=595.28, height=841.89,
#             spans=spans,
#             lines=[{"text": "Sample body text.", "bbox": [50, 100, 545, 115]}],
#             heading_candidates=heading_candidates,
#         )
#         return _make_doc(
#             full_text=text,
#             dominant_font="TimesNewRomanPSMT",
#             dominant_size=10.0,
#             page_count=8,
#             pages=[page],
#         )

#     def test_returns_list(self):
#         doc    = self._full_doc()
#         result = check_formatting(doc, "IEEE")
#         self.assertIsInstance(result, list)

#     def test_geometry_skipped_in_lenient_mode(self):
#         """
#         In lenient (published) mode, geometry checks are soft.
#         A doc with wrong margins should not produce geometry 'warning' issues.
#         """
#         doc    = self._full_doc()
#         result = check_formatting(doc, "IEEE", paper_type="other", review_mode="published")
#         geom_warnings = [
#             i for i in result
#             if i["severity"] == "warning" and i["category"] == "formatting"
#             and ("margin" in i["id"] or "page-size" in i["id"])
#         ]
#         self.assertEqual(geom_warnings, [],
#                          "Published-paper mode should not produce geometry warnings")

#     def test_strict_mode_runs_geometry(self):
#         """
#         In conference_submission mode with a bad font, a font warning should appear.
#         """
#         doc = self._full_doc()
#         doc["dominant_font"] = "Arial"   # wrong font for IEEE
#         result = check_formatting(doc, "IEEE", paper_type="conference_submission")
#         ids = _ids(result)
#         self.assertIn("font-body-mismatch", ids)

#     def test_sorted_by_page(self):
#         """Issues should be sorted: page 1 before page 2, doc-level last."""
#         doc    = self._full_doc()
#         result = check_formatting(doc, "IEEE")
#         pages  = [i["page"] for i in result]
#         for i in range(len(pages) - 1):
#             a = pages[i]   if pages[i]   is not None else 9999
#             b = pages[i+1] if pages[i+1] is not None else 9999
#             self.assertLessEqual(a, b, "Issues should be sorted by page number")

#     def test_new_checks_run(self):
#         """
#         The two new checks (sentence length + equations) should always run.
#         Create a doc that will trigger both.
#         """
#         # 60+ words with a period so the sentence splitter picks it up
#         long_sent = " ".join(["word"] * 70) + "."
#         eq_text   = " We define\n  f(x)  (1)\nbut never cite it."
#         doc = _make_doc(full_text=long_sent + eq_text)
#         result = check_formatting(doc, "IEEE")
#         ids = _ids(result)
#         self.assertTrue(
#             any("sentence-too-long" in i for i in ids),
#             "Sentence-length check should run and flag the long sentence"
#         )
#         self.assertIn("equation-unreferenced", ids,
#                       "Equation check should run and flag unlabelled equation")


# class TestGetStandard(unittest.TestCase):
#     """
#     Quick sanity checks that the standards config loads correctly.
#     These are fast — no PDF needed.
#     """

#     def test_ieee_loads(self):
#         rules = get_standard("IEEE")
#         self.assertIsNotNone(rules)
#         self.assertEqual(rules["body_size"], 10.0)

#     def test_case_insensitive(self):
#         self.assertIsNotNone(get_standard("ieee"))
#         self.assertIsNotNone(get_standard("Ieee"))

#     def test_neurips_alias(self):
#         """'NEURIPS' (all caps) should resolve to the NeurIPS standard."""
#         rules = get_standard("NEURIPS")
#         self.assertIsNotNone(rules)

#     def test_unknown_standard_returns_none(self):
#         self.assertIsNone(get_standard("TOTALLY_FAKE_VENUE"))

#     def test_all_standards_have_required_keys(self):
#         """Every standard must have the core keys that check_formatting() reads."""
#         from backend.configs.format_rules import STANDARDS
#         from backend.modules.format_checker import _resolve_margin

#         always_required = ["body_size", "columns", "required_sections"]
#         for name, rules in STANDARDS.items():
#             for key in always_required:
#                 self.assertIn(key, rules,
#                               f"Standard '{name}' is missing required key '{key}'")
#             # Margins may use any of three conventions — verify at least one exists
#             for side in ("top", "bottom", "left", "right"):
#                 val = _resolve_margin(rules, side)
#                 self.assertIsNotNone(
#                     val,
#                     f"Standard '{name}' has no margin value for side '{side}' "
#                     f"(checked margin_{side}, margin_{side}_pts, margin_{side}_cm)"
#                 )


# # ══════════════════════════════════════════════════════════════════════════════
# # ENTRY POINT
# # ══════════════════════════════════════════════════════════════════════════════

# if __name__ == "__main__":
#     # Run with verbose output so you see every test name
#     unittest.main(verbosity=2)

import sys
import os

# Ensure the project root is in the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the orchestrator we just saw in your code
from modules.format_checker import run_format_check

def test_faulty_paper():
    # 1. Path to your uploaded faulty PDF
    pdf_name = "faulty_paper.pdf"
    pdf_path = os.path.join("tests", "sample_papers", pdf_name)
    
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found. Ensure it is in tests/sample_papers/")
        return

    print(f"\n{'='*60}")
    print(f"TESTING: {pdf_name} USING run_format_check")
    print(f"{'='*60}")

    try:
        # 2. Call the high-level helper. This function:
        #    a) Extracts raw elements using extract_structure
        #    b) Groups them into the 'parsed_document' dict
        #    c) Runs the formatting logic
        result = run_format_check(
            pdf_path=pdf_path,
            standard="IEEE",
            paper_type="conference_submission"
        )

        # 3. Print the results
        print(f"Summary: {result['summary']}\n")
        
        if not result['issues']:
            print("No issues found! 🎉")
        else:
            for issue in result['issues']:
                loc = f"Page {issue['page']}" if issue['page'] else "Doc-level"
                print(f"- [{issue['severity'].upper()}] {loc}: {issue['message']}")
                print(f"  Suggestion: {issue['suggestion']}\n")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    test_faulty_paper()