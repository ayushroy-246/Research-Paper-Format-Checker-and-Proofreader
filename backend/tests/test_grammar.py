# """
# tests/test_grammar.py
# =====================
# Manual smoke-test for modules/grammar_checker.py.

# Run from the project root:
#     python tests/test_grammar.py

# Expected: 7+ issues detected across the three layers.
# """

# import os
# import sys
# import json

# # ---------------------------------------------------------------------------
# # Path fix: add project root so "from modules.grammar_checker" resolves
# # ---------------------------------------------------------------------------
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from modules.grammar_checker import check_grammar

# # ---------------------------------------------------------------------------
# # Mock parsed_doc — mirrors the shape produced by pdf_ingestion.py
# # Each page exercises a different subset of checks so we can verify coverage.
# # ---------------------------------------------------------------------------
# mock_parsed_doc = {
#     "metadata": {"filename": "test_paper.pdf", "total_pages": 2},
#     "pages": [
#         {
#             "page_number": 1,
#             "text": (
#                 # Layer 1 – contraction + repeated word
#                 "However, the the processor can't handle the load. "
#                 # Layer 2 – spelling error (recieve)
#                 "The server will recieve the data [14]. "
#                 # Normalizer – equation stripped before checking
#                 "Let $x = 5$ be the variable. "
#                 # Layer 3 – subjective first-person phrase
#                 "I believe this algorithm is highly efficient. "
#                 # Layer 3 – overconfident claim
#                 "This clearly shows that our method is superior."
#             )
#         },
#         {
#             "page_number": 2,
#             "text": (
#                 # Layer 1 – first-person pronoun
#                 "We conducted several experiments to validate our approach. "
#                 # Layer 3 – vague quantifier ("several") + active voice near experiment kw
#                 "We found that the results improve accuracy on the dataset. "
#                 # Layer 3 – unhedged claim (no hedge word nearby)
#                 "This method performs well under all conditions. "
#                 # Layer 3 – unsupported superlative
#                 "Our framework is the best solution available. "
#                 # Normalizer – citation stripped, DOI stripped
#                 "As noted in (Smith, 2024), doi:10.1234/xyz the approach is sound."
#             )
#         }
#     ]
# }

# # ---------------------------------------------------------------------------
# # Runner
# # ---------------------------------------------------------------------------
# if __name__ == "__main__":
#     print("=" * 60)
#     print("  Grammar Module Smoke Test")
#     print("=" * 60)
#     print("Starting LanguageTool Java server (may take ~10 s)...\n")

#     issues = check_grammar(mock_parsed_doc)

#     print(f"Scan complete.  {len(issues)} issue(s) found.\n")

#     if not issues:
#         print("[WARN] No issues returned — check that LanguageTool is installed")
#         print("       and that the mock text above is reaching the layers.")
#         sys.exit(1)

#     print(json.dumps(issues, indent=4))

#     # ---------------------------------------------------------------------------
#     # Basic assertions — fail loudly if the schema breaks
#     # ---------------------------------------------------------------------------
#     required_keys = {"id", "category", "severity", "page", "message", "suggestion"}
#     valid_severities = {"critical", "warning", "info"}
#     schema_errors = []

#     for i, issue in enumerate(issues):
#         missing = required_keys - issue.keys()
#         if missing:
#             schema_errors.append(f"Issue #{i}: missing keys {missing}")
#         if issue.get("severity") not in valid_severities:
#             schema_errors.append(
#                 f"Issue #{i}: invalid severity '{issue.get('severity')}'"
#             )
#         if issue.get("category") != "grammar":
#             schema_errors.append(
#                 f"Issue #{i}: expected category='grammar', got '{issue.get('category')}'"
#             )

#     print("\n" + "=" * 60)
#     if schema_errors:
#         print(f"SCHEMA FAILURES ({len(schema_errors)}):")
#         for err in schema_errors:
#             print(f"  - {err}")
#         sys.exit(1)
#     else:
#         print(f"All {len(issues)} issues passed schema validation.")
#         print("Smoke test PASSED.")


# import sys
# import os

# # Add the project root to the path so we can import our modules
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# from modules.grammar_checker import check_grammar, assemble_doc_from_spans

# def test_integration_flow():
#     print("=" * 60)
#     print("  Grammar Module Integration Test (Span-to-Issue)")
#     print("=" * 60)

#     # 1. MOCK DATA: This mimics the exact list of dicts your friend's 
#     # pdf_ingestion.extract_structure() function returns.
#     mock_spans = [
#         # Page 1 Spans
#         {"page": 1, "text": "The results "},
#         {"page": 1, "text": "clearly shows "}, # Layer 3: Overconfident
#         {"page": 1, "text": "that the the "},   # Layer 1: Repeated word
#         {"page": 1, "text": "algorithm is "},   # Layer 3: Missing hedge
#         {"page": 1, "text": "the best."},       # Layer 3: Superlative
        
#         # Page 2 Spans
#         {"page": 2, "text": "We found "},       # Layer 3: Active voice
#         {"page": 2, "text": "several "},         # Layer 3: Vague quantifier
#         {"page": 2, "text": "errors in the "},
#         {"page": 2, "text": "recieve process."}  # Layer 2: Spelling (LanguageTool)
#     ]

#     print("Step 1: Assembling spans into page-based format...")
#     # This calls your new Bridge/Assembler function
#     formatted_doc = assemble_doc_from_spans(mock_spans)
    
#     print("Step 2: Running multi-layer grammar check...")
#     results = check_grammar(formatted_doc)

#     print(f"\nScan complete. {len(results)} issue(s) found.\n")

#     # Quick validation of the results
#     for issue in results:
#         print(f"[{issue['severity'].upper()}] Page {issue['page']}: {issue['message']}")
#         print(f"   Suggestion: {issue['suggestion']}\n")

#     if len(results) > 0:
#         print("=" * 60)
#         print("Integration Test PASSED.")
#     else:
#         print("Integration Test FAILED: No issues detected.")

# if __name__ == "__main__":
#     test_integration_flow()

"""
tests/test_grammar.py
=====================
Integration smoke-test for modules/grammar_checker.py.

Reads a real PDF from tests/sample_papers/, runs the full 3-layer
grammar pipeline, and prints every issue with its page and snippet.

Run from the project root:
    python tests/test_grammar.py
"""

import os
import sys
import json

# ---------------------------------------------------------------------------
# Path fix: add project root so module imports resolve correctly
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from modules.grammar_checker import check_grammar, assemble_doc_from_spans
from modules.pdf_ingestion import extract_structure

# ---------------------------------------------------------------------------
# Config — change only this line if you want to test a different paper
# ---------------------------------------------------------------------------
PDF_PATH = os.path.join(PROJECT_ROOT, "tests", "sample_papers", "test_paper_faulty_grammar.pdf")

# ===========================================================================
# Runner
# ===========================================================================
if __name__ == "__main__":
    print("=" * 65)
    print("  Grammar Module Integration Test")
    print("=" * 65)

    # --- Guard: check the PDF actually exists before doing anything ---
    if not os.path.exists(PDF_PATH):
        print(f"\n[ERROR] PDF not found at:\n  {PDF_PATH}")
        print("\nMake sure you have:")
        print("  tests/")
        print("  └── sample_papers/")
        print("      └── test_paper.pdf")
        sys.exit(1)

    print(f"\nPDF  : {PDF_PATH}")

    # --- Step 1: Extract spans from PDF (pdf_ingestion) ---
    print("\nStep 1: Extracting spans from PDF...")
    spans = extract_structure(PDF_PATH)
    print(f"         {len(spans)} spans extracted across all pages.")

    # --- Step 2: Assemble spans into page-based format ---
    print("Step 2: Assembling spans into page-based format...")
    formatted_doc = assemble_doc_from_spans(spans)
    num_pages = len(formatted_doc.get("pages", []))
    print(f"         {num_pages} page(s) assembled.")

    # --- Step 3: Run grammar checker (all 3 layers) ---
    print("Step 3: Running grammar checker")
    print("        (LanguageTool Java server may take ~10 s to start...)\n")
    issues = check_grammar(formatted_doc)

    # ---------------------------------------------------------------------------
    # Results
    # ---------------------------------------------------------------------------
    print("=" * 65)
    print(f"  Scan complete — {len(issues)} issue(s) found")
    print("=" * 65)

    if not issues:
        print("\n[WARN] No issues returned.")
        print("  - Check LanguageTool is installed: pip install language-tool-python")
        print("  - Check the PDF has extractable text (not a scanned image)")
        sys.exit(1)

    # Group issues by page for readable output
    from collections import defaultdict
    by_page = defaultdict(list)
    for issue in issues:
        by_page[issue["page"]].append(issue)

    for page_num in sorted(by_page.keys(), key=lambda x: (x is None, x)):
        page_label = f"Page {page_num}" if page_num is not None else "Page Unknown"
        page_issues = by_page[page_num]
        print(f"\n── {page_label}  ({len(page_issues)} issue(s)) " + "─" * 30)
        for issue in page_issues:
            severity_tag = f"[{issue['severity'].upper()}]"
            snippet_str  = f"  snippet : \"{issue['snippet']}\"" if issue.get("snippet") else ""
            print(f"\n  {severity_tag}  {issue['id']}")
            if snippet_str:
                print(f"  {snippet_str}")
            print(f"  message : {issue['message']}")
            print(f"  fix     : {issue['suggestion']}")

    # ---------------------------------------------------------------------------
    # Schema validation — ensures every issue has all required keys
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("  Schema Validation")
    print("=" * 65)

    REQUIRED_KEYS    = {"id", "category", "severity", "page", "snippet", "message", "suggestion"}
    VALID_SEVERITIES = {"critical", "warning", "info"}
    errors = []

    for i, issue in enumerate(issues):
        missing = REQUIRED_KEYS - issue.keys()
        if missing:
            errors.append(f"Issue #{i}: missing keys {missing}")
        if issue.get("severity") not in VALID_SEVERITIES:
            errors.append(f"Issue #{i}: invalid severity '{issue.get('severity')}'")
        if issue.get("category") != "grammar":
            errors.append(f"Issue #{i}: expected category='grammar', got '{issue.get('category')}'")

    if errors:
        print(f"\n[FAIL] {len(errors)} schema error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"\n[PASS] All {len(issues)} issues passed schema validation.")

    # ---------------------------------------------------------------------------
    # Summary by severity
    # ---------------------------------------------------------------------------
    from collections import Counter
    counts = Counter(issue["severity"] for issue in issues)
    print("\n  Severity breakdown:")
    print(f"    critical : {counts.get('critical', 0)}")
    print(f"    warning  : {counts.get('warning',  0)}")
    print(f"    info     : {counts.get('info',     0)}")
    print("\n  Smoke test PASSED.")