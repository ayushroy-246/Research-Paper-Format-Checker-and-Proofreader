"""
app.py
======
Flask backend — central orchestrator for the Research Paper Checker.

Pipeline:
    React FE  →  POST /api/upload   →  pdf_ingestion  (Member 1)
              →  POST /api/analyze  →  grammar_checker (Member 3)
                                    →  format_checker  (Member 2)
                                    →  citation_checker(Member 4)
              →  POST /api/generate-report  →  report_generator (Member 5) [WIP]

API Endpoints:
    GET  /api/health          → server health check
    POST /api/upload          → upload PDF, extract structure, save outputs
    POST /api/analyze         → run all checks on the uploaded PDF
    POST /api/generate-report → generate final report [placeholder — WIP]
"""

import os
import json
import sys

from flask import Flask, request, jsonify
from flask_cors import CORS  # Cross-Origin Resource Sharing
from dotenv import load_dotenv  # Load environment variables from .env

# ── Add backend/ to sys.path so all module imports work correctly ─────────────
sys.path.insert(0, os.path.dirname(__file__))

# ── Import all modules ────────────────────────────────────────────────────────
from modules.pdf_ingestion   import extract_structure, save_json
from modules.grammar_checker import check_grammar
from modules.format_checker  import run_format_check   # one-shot helper — handles everything internally
from modules.citation_checker import check_citations

# ── Load environment variables from .env file ─────────────────────────────────
load_dotenv()

# ── Flask App Setup ───────────────────────────────────────────────────────────
app = Flask(__name__)

# ── Configure CORS to only allow the frontend URL from .env ──────────────────
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
CORS(app, resources={
    r"/api/*": {
        "origins": [FRONTEND_URL],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"],
        "supports_credentials": True
    }
})
print(f"[INFO] CORS enabled for: {FRONTEND_URL}")

# ── Fixed output paths (relative to backend/) ────────────────────────────────
OUTPUTS_DIR      = os.path.join(os.path.dirname(__file__), "outputs")
EXTRACTED_JSON   = os.path.join(OUTPUTS_DIR, "extracted_data.json")   # span list — only output file
UPLOADED_PDF     = os.path.join(OUTPUTS_DIR, "uploaded.pdf")          # saved for format_checker


# =============================================================================
# ROUTE: Health Check
# =============================================================================

@app.route("/api/health", methods=["GET"])
def health():
    """Quick ping so the React FE can confirm the server is alive."""
    return jsonify({
        "status":  "ok",
        "message": "Research Paper Checker API is running."
    })


# =============================================================================
# ROUTE: Upload PDF
# =============================================================================

@app.route("/api/upload", methods=["POST"])
def upload():
    """
    Step 1 — Receive a PDF from React FE, extract its structure,
    and save output files that all other modules will read from.

    Request:  multipart/form-data  →  field name: 'file'  (PDF only)

    Response:
        {
            "status":     "extracted",
            "page_count": int,      ← number of pages in the PDF
            "span_count": int,      ← total text spans extracted
            "message":    str
        }
    """
    # ── Validate request ──
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Send a PDF in the 'file' field."}), 400

    pdf_file = request.files["file"]
    if not pdf_file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are accepted."}), 400

    # ── Save uploaded PDF to outputs/ so analyze can reuse it later ──
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    pdf_file.save(UPLOADED_PDF)

    try:
        # ── Run Member 1's extraction ──
        spans = extract_structure(UPLOADED_PDF)

        if not spans:
            return jsonify({"error": "PDF appears to be empty or has no extractable text."}), 422

        # ── Save the span JSON — only output file needed ──
        save_json(spans, EXTRACTED_JSON)   # → extracted_data.json

        return jsonify({
            "status":     "extracted",
            "page_count": spans[-1]["page"],
            "span_count": len(spans),
            "message":    "PDF extracted successfully. Call POST /api/analyze to run checks.",
        })

    except Exception as e:
        # Clean up the saved PDF if extraction fails
        if os.path.exists(UPLOADED_PDF):
            os.remove(UPLOADED_PDF)
        return jsonify({"error": f"Extraction failed: {str(e)}"}), 500


# =============================================================================
# ROUTE: Analyze (run all checks)
# =============================================================================

@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Step 2 — Run grammar, format, and citation checks on the previously uploaded PDF.

    Request body (JSON):
        {
            "standard":    "IEEE" | "APA" | "ACL" | "Springer" | ...  (default: "IEEE")
            "paper_type":  "conference_submission" | "journal" | "arxiv" | null
            "review_mode": "blind" | "camera_ready" | "published" | null
            "use_crossref": true | false   (default: true — calls Crossref API)
        }

    Response:
        {
            "status":       "analyzed",
            "standard":     str,
            "total_issues": int,
            "issues": {
                "grammar":    [ ...issue dicts... ],
                "formatting": [ ...issue dicts... ],
                "citations":  [ ...issue dicts... ],
                "errors":     [ ...any module crash reports... ]
            },
            "summary": {
                "total": int, "critical": int, "warning": int, "info": int, "score": int
            }
        }
    """
    # ── Check that upload was called first ──
    if not os.path.exists(EXTRACTED_JSON):
        return jsonify({
            "error": "No extracted data found. Please upload a PDF first via POST /api/upload."
        }), 400

    if not os.path.exists(UPLOADED_PDF):
        return jsonify({
            "error": "Uploaded PDF not found. Please re-upload the PDF via POST /api/upload."
        }), 400

    # ── Parse request body ──
    body         = request.get_json(silent=True) or {}
    standard     = body.get("standard", "IEEE").strip().upper()
    paper_type   = body.get("paper_type")
    review_mode  = body.get("review_mode")
    use_crossref = body.get("use_crossref", True)

    # ── Load pre-extracted span list ──
    f = open(EXTRACTED_JSON, encoding="utf-8")
    try:
        spans = json.load(f)    # list of span dicts from extracted_data.json
    finally:
        f.close()

    # ── Build page-indexed text in-memory (no file needed) ──
    # {"1": "text of page 1", "2": "text of page 2", ...}
    page_texts: dict[str, str] = {}
    for span in spans:
        key = str(span["page"])                             # use string keys to match JSON convention
        page_texts[key] = page_texts.get(key, "") + span["text"] + " "

    # Flat text for citation_checker (needs the whole document as one string)
    full_text = " ".join(page_texts.values())

    issues = {"grammar": [], "formatting": [], "citations": [], "errors": []}

    # ── Grammar check (Member 3) ──
    # Pass spans directly — grammar_checker has assemble_doc_from_spans() built-in for this
    try:
        issues["grammar"] = check_grammar(spans)
    except Exception as e:
        issues["errors"].append({"module": "grammar_checker", "error": str(e)})

    # ── Format check (Member 2) ──
    # run_format_check() handles extraction internally using the saved PDF
    try:
        format_result       = run_format_check(UPLOADED_PDF, standard, paper_type, review_mode)
        issues["formatting"] = format_result.get("issues", [])
    except Exception as e:
        issues["errors"].append({"module": "format_checker", "error": str(e)})

    # ── Citation check (Member 4) ──
    # parsed_document=spans — citation_checker expects the raw span list for page lookup
    try:
        issues["citations"] = check_citations(
            full_text=full_text,
            standard=standard,
            paper_type=paper_type,
            parsed_document=spans,       # raw span list — citation_checker uses this for page lookup
            use_crossref=use_crossref,
        )
    except Exception as e:
        issues["errors"].append({"module": "citation_checker", "error": str(e)})

    # ── Build summary counts and calculate score ──
    all_issues = issues["grammar"] + issues["formatting"] + issues["citations"]
    
    critical_count = sum(1 for i in all_issues if i.get("severity") == "critical")
    warning_count = sum(1 for i in all_issues if i.get("severity") == "warning")
    info_count = sum(1 for i in all_issues if i.get("severity") == "info")

    # Calculate score based on weighted deductions with logarithmic scaling
    # Cap critical/warning at 20 each to prevent scores from hitting 0 easily
    capped_critical = min(critical_count, 20)
    capped_warning = min(warning_count, 20)
    capped_info = min(info_count, 30)
    
    # Reduced weights: less harsh penalty per issue
    score = 100 - (capped_critical * 3) - (capped_warning * 1) - (capped_info * 0.3)
    
    summary = {
        "total":    len(all_issues),
        "critical": critical_count,
        "warning":  warning_count,
        "info":     info_count,
        "score":    max(0, score)  # Ensure score doesn't go below 0
    }

    return jsonify({
        "status":       "analyzed",
        "standard":     standard,
        "total_issues": summary["total"],
        "issues":       issues,
        "summary":      summary,
    })


# =============================================================================
# ROUTE: Generate Report [PLACEHOLDER — report_generator.py is WIP]
# =============================================================================

@app.route("/api/generate-report", methods=["POST"])
def generate_report():
    """
    Step 3 — Generate a downloadable PDF/HTML report.

    NOTE: report_generator.py is being built by Member 5.
    This endpoint returns 501 until that module is ready.
    Once ready, Member 5 should:
        1. Import their function here
        2. Replace the body of this function with the actual report logic
    """
    return jsonify({
        "status":  "not_implemented",
        "message": "report_generator.py is under development by Member 5. Check back soon.",
    }), 501


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    app.run(debug=True, port=5000)