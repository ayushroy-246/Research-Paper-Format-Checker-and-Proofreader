"""
tests/test_citation.py
======================
Integration test for modules/citation_checker.py.

Reads a real PDF from tests/sample_papers/, extracts text and spans via
pdf_ingestion, then runs the full citation checker pipeline and prints
every issue found.

Run from the project root:
    python tests/test_citation.py

Expected: 6-8 issues for faulty_citation_ieee_paper.pdf (IEEE standard).
"""

import os
import sys
from collections import Counter

# ---------------------------------------------------------------------------
# Path fix: add project root so module imports resolve correctly
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from modules.pdf_ingestion import extract_structure
from modules.citation_checker import check_citations

# ---------------------------------------------------------------------------
# Config — change only these two lines to test a different paper
# ---------------------------------------------------------------------------
PDF_PATH  = os.path.join(PROJECT_ROOT, "tests", "sample_papers", "faulty_citation_ieee_paper.pdf")
STANDARD  = "IEEE"          # "IEEE" | "APA" | "ACL" | "Springer" | "NeurIPS" etc.
USE_CROSSREF = True        # Set False to skip internet API calls (faster, offline)

# ===========================================================================
# Runner
# ===========================================================================
if __name__ == "__main__":
    print("=" * 65)
    print("  Citation Checker Integration Test")
    print("=" * 65)

    # --- Guard: check the PDF actually exists ---
    if not os.path.exists(PDF_PATH):
        print(f"\n[ERROR] PDF not found at:\n  {PDF_PATH}")
        print("\nMake sure you have:")
        print("  tests/")
        print("  └── sample_papers/")
        print("      └── faulty_citation_ieee_paper.pdf")
        sys.exit(1)

    print(f"\nPDF      : {PDF_PATH}")
    print(f"Standard : {STANDARD}")
    print(f"Crossref : {'enabled' if USE_CROSSREF else 'disabled'}\n")

    # --- Step 1: Extract spans (pdf_ingestion) ---
    print("Step 1: Extracting spans from PDF...")
    spans = extract_structure(PDF_PATH)
    print(f"         {len(spans)} spans extracted.")

    # --- Step 2: Build full_text (join all span texts) ---
    print("Step 2: Building full text from spans...")
    full_text = "\n".join(span["text"] for span in spans)
    print(f"         {len(full_text)} characters extracted.")

    # --- Step 3: Run citation checker ---
    print("Step 3: Running citation checker")
    if USE_CROSSREF:
        print("        (Crossref API calls active — may take 10-30 s...)\n")
    else:
        print("        (Crossref disabled — running offline)\n")

    issues = check_citations(
        full_text       = full_text,
        standard        = STANDARD,
        paper_type      = None,
        parsed_document = spans,        # flat span list from pdf_ingestion
        use_crossref    = USE_CROSSREF,
    )

    # ---------------------------------------------------------------------------
    # Results — grouped by page
    # ---------------------------------------------------------------------------
    print("=" * 65)
    print(f"  Scan complete — {len(issues)} issue(s) found")
    print("=" * 65)

    if not issues:
        print("\n[WARN] No issues returned.")
        print("  - Verify the PDF has extractable text (not a scanned image)")
        print("  - Verify STANDARD matches the paper's citation style")
        sys.exit(1)

    # Group by page for readable output
    from collections import defaultdict
    by_page = defaultdict(list)
    for issue in issues:
        by_page[issue.get("page")].append(issue)

    for page_num in sorted(by_page.keys(), key=lambda x: (x is None, x)):
        page_label  = f"Page {page_num}" if page_num is not None else "Document-level"
        page_issues = by_page[page_num]
        print(f"\n── {page_label}  ({len(page_issues)} issue(s)) " + "─" * 28)

        for issue in page_issues:
            severity_tag = f"[{issue['severity'].upper()}]"
            print(f"\n  {severity_tag}  {issue['id']}")
            print(f"  message    : {issue['message']}")
            print(f"  suggestion : {issue['suggestion']}")

    # ---------------------------------------------------------------------------
    # Schema validation
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("  Schema Validation")
    print("=" * 65)

    REQUIRED_KEYS    = {"id", "category", "severity", "page", "message", "suggestion", "location"}
    VALID_SEVERITIES = {"error", "warning", "info"}
    schema_errors    = []

    for i, issue in enumerate(issues):
        missing = REQUIRED_KEYS - issue.keys()
        if missing:
            schema_errors.append(f"Issue #{i} ({issue.get('id','?')}): missing keys {missing}")
        if issue.get("severity") not in VALID_SEVERITIES:
            schema_errors.append(
                f"Issue #{i}: invalid severity '{issue.get('severity')}'"
            )
        if issue.get("category") != "citations":
            schema_errors.append(
                f"Issue #{i}: expected category='citations', got '{issue.get('category')}'"
            )

    if schema_errors:
        print(f"\n[FAIL] {len(schema_errors)} schema error(s):")
        for e in schema_errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"\n[PASS] All {len(issues)} issues passed schema validation.")

    # ---------------------------------------------------------------------------
    # Severity summary
    # ---------------------------------------------------------------------------
    counts = Counter(issue["severity"] for issue in issues)
    print("\n  Severity breakdown:")
    print(f"    error   : {counts.get('error',   0)}")
    print(f"    warning : {counts.get('warning', 0)}")
    print(f"    info    : {counts.get('info',    0)}")
    print("\n  Citation test PASSED.")