#!/usr/bin/env python3
"""Extract text from PDFs for analysis."""
import pdfplumber
import json
from pathlib import Path

def extract_pdf_text(pdf_path, output_path):
    """Extract text from PDF and save to file."""
    text_parts = []
    metadata = {}

    try:
        with pdfplumber.open(pdf_path) as pdf:
            metadata = {
                'pages': len(pdf.pages),
                'file': pdf_path.name
            }
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    text_parts.append(f"--- Page {i+1} ---\n{text}")
    except Exception as e:
        metadata['error'] = str(e)

    full_text = "\n\n".join(text_parts)

    # Save text
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(full_text)

    return metadata

# Directories
rc_dir = Path("/home/michka/Documents/0-AO-DCE/public/rc")
rapport_dir = Path("/home/michka/Documents/0-AO-DCE/public/analyse-ao")
output_dir = Path("/home/michka/Documents/0-AO-DCE/data/intermediate/pdf_extracts")
output_dir.mkdir(parents=True, exist_ok=True)

results = {'rc': {}, 'rapports': {}}

# Extract RCs
for pdf_file in rc_dir.glob("*.pdf"):
    output_file = output_dir / f"{pdf_file.stem}.txt"
    meta = extract_pdf_text(pdf_file, output_file)
    results['rc'][pdf_file.name] = meta
    print(f"Extracted: {pdf_file.name} -> {output_file}")

# Extract Rapports
for pdf_file in rapport_dir.glob("*.pdf"):
    output_file = output_dir / f"{pdf_file.stem}.txt"
    meta = extract_pdf_text(pdf_file, output_file)
    results['rapports'][pdf_file.name] = meta
    print(f"Extracted: {pdf_file.name} -> {output_file}")

# Save summary
with open(output_dir / "extraction_summary.json", 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("\nExtraction complete!")
