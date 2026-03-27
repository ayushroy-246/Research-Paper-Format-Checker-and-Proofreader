import pymupdf
import json
import os


def extract_structure(pdf_path: str) -> list:
    """
    Extracts structured text data from a PDF file.
    Returns a list of dicts, one per text span.
    """
    results = []

    doc = pymupdf.open(pdf_path)  # doc becomes a document object — think of it like a list of pages.
    for page in doc:
        page_number = page.number + 1  # pymupdf uses 0-index, we want 1-index
        width = page.rect.width  # page.rect.width/height give use the dimensions of the page in points (1 point = 1/72 inch = 0.0352778 cm)
        height = page.rect.height

        blocks = page.get_text("dict")["blocks"]  # returns nested dicts: page → blocks → lines → spans
        for block in blocks:
            if block["type"] != 0:  # PyMuPDF marks text=0, image=1; we only want text blocks
                continue
            for line in block["lines"]:  # each block has multiple lines (list of line dicts)
                for span in line["spans"]:  # each line has multiple spans — one span = one consistently styled chunk of text

                    # span["flags"] is an integer where each bit encodes a style.
                    # Bit 4 (value 16 = 2**4) means bold. We use bitwise AND (&) to check if that bit is ON.
                    # e.g. flags=20 (binary: 10100) → 20 & 16 = 16 (truthy) → bold=True
                    bold = bool(span["flags"] & 2**4)

                    # span["bbox"] is automatically provided by PyMuPDF — it's the bounding box
                    # (the rectangle) that wraps this span on the page: (x0, y0, x1, y1)
                    # x0,y0 = top-left corner; x1,y1 = bottom-right corner (in points from top-left of page)
                    span_data = {
                        "page": page_number,
                        "text": span["text"],           # the actual text string
                        "font": span["font"],           # font name e.g. "TimesNewRoman-Bold"
                        "size": span["size"],           # font size in points (e.g. 12.0)
                        "bold": bold,                   # True/False decoded from flags
                        "x0": span["bbox"][0],          # left edge of this text on the page
                        "y0": span["bbox"][1],          # top edge
                        "x1": span["bbox"][2],          # right edge
                        "y1": span["bbox"][3],          # bottom edge
                        "page_width": width,            # full page width (used by other modules to compute margins)
                        "page_height": height           # full page height (used to detect headers/footers)
                    }

                    results.append(span_data)  # add this span's dict to our list 


    return results


def save_full_text(data : list, output_path: str) -> None:
    """
    Combines all the span text info on plain text file.
    data: the list returned by extract_structure()
    output_path: where to save the .txt file
    """

    os.makedirs(os.path.dirname(output_path), exist_ok=True) # create outputs/ folder if it doesn't exist 

    full_text = " ".join(span["text"] for span in data) # join all span texts with a space  JS: data.map(span => span.text).join(" ")

    
    f = open(output_path, "w", encoding="utf-8")
    try: 
        f.write(full_text)
    finally:
        f.close()

def save_json(data: list, output_path: str) -> None:
    """
    Saves the extracted span data as a JSON file.
    data: the list returned by extract_structure()
    output_path: where to save the .json file
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)  # create outputs/ folder if it doesn't exist (exist_ok=True means no crash if already exists)

    f = open(output_path, "w", encoding="utf-8")  # open file in write mode; "w" creates it if not exists, overwrites if it does
    try:
        # json.dump → converts Python list of dicts to JSON and writes directly to file f
        # indent=2 → pretty-prints with 2-space indentation (like JSON.stringify(data, null, 2) in JS)
        # ensure_ascii=False → saves non-English characters (é, ü, etc.) as-is instead of escaping them
        json.dump(data, f, indent=2, ensure_ascii=False)
    finally:
        f.close()  # always close the file, even if json.dump fails

