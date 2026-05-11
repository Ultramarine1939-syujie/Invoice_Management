"""Print extracted text from local PDF samples for parser debugging."""

from __future__ import annotations

import argparse
from pathlib import Path

import pdfplumber


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_dir", type=Path, help="Directory containing PDF files")
    parser.add_argument("--chars", type=int, default=3000, help="Characters to print per file")
    args = parser.parse_args()

    for pdf_path in sorted(args.pdf_dir.glob("*.pdf")):
        print(f"\n=== {pdf_path.name} ===")
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = "\n".join(filter(None, (page.extract_text() for page in pdf.pages)))
            print(text[: args.chars])
            if len(text) > args.chars:
                print("\n... [truncated]")
        except Exception as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()
