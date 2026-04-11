import sys
import os

# Add backend/ to Python's import search path so we can import from modules/
# (this file lives in tests/, but our module is in modules/ — one level up)
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Import the 2 functions we need from pdf_ingestion.py
from modules.pdf_ingestion import extract_structure, save_json

# --- File Paths ---
# __file__ = path of this script; os.path.dirname gives us its folder (tests/)
# os.path.join builds cross-platform paths safely (no hardcoded / or \)
PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "sample.pdf"
)  # sample.pdf is at the project root (two levels up from tests/)
JSON_OUTPUT = os.path.join(
    os.path.dirname(__file__), "..", "outputs", "extracted_data.json"
)  # ".." goes up to backend/, then into outputs/

# --- Step 1: Extract structure from the PDF ---
print("Extracting structure from PDF...")
data = extract_structure(PDF_PATH)  # returns a list of dicts — one dict per text span

# --- Step 2: Sanity check ---
print(
    "Total spans extracted:", len(data)
)  # total number of text spans found across all pages
print(
    "First span:", data[0]
)  # print first span to verify our JSON structure is correct

# --- Step 3: Save outputs for other modules to consume ---
print("\nSaving outputs...")
save_json(data, JSON_OUTPUT)  # saves list of span dicts → extracted_data.json
print("Done! Check backend/outputs/extracted_data.json")
