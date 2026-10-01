#!/usr/bin/env python3
"""
MarkItDown Helper Script
Supports converting a single file or a batch of files into Markdown.
"""

import argparse
import os
import sys
from pathlib import Path
from markitdown import MarkItDown

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
    ".html", ".htm", ".csv", ".json", ".xml", ".zip",
    ".wav", ".mp3", ".m4a", ".jpg", ".jpeg", ".png", ".bmp", ".tiff"
}

def convert_single_file(converter: MarkItDown, input_path: Path, output_path: Path = None) -> bool:
    try:
        print(f"Converting: {input_path} ...", end=" ", flush=True)
        result = converter.convert(str(input_path))
        markdown_text = result.text_content

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_text)
            print(f"Saved -> {output_path} ({len(markdown_text)} chars)")
        else:
            print("\n" + "=" * 60)
            print(markdown_text)
            print("=" * 60)
        return True
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return False

def convert_directory(converter: MarkItDown, input_dir: Path, output_dir: Path, recursive: bool = False):
    pattern = "**/*" if recursive else "*"
    files = [p for p in input_dir.glob(pattern) if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]

    if not files:
        print(f"No supported files found in {input_dir}")
        return

    print(f"Found {len(files)} file(s) to convert.")
    output_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    for file_path in files:
        if recursive:
            rel_path = file_path.relative_to(input_dir)
            out_file = output_dir / rel_path.with_suffix(".md")
        else:
            out_file = output_dir / f"{file_path.stem}.md"

        if convert_single_file(converter, file_path, out_file):
            success_count += 1

    print(f"\nBatch conversion finished: {success_count}/{len(files)} files successfully converted.")

def main():
    parser = argparse.ArgumentParser(description="Convert files or folders to Markdown using Microsoft MarkItDown.")
    parser.add_argument("-i", "--input", required=True, help="Input file or directory path")
    parser.add_argument("-o", "--output", help="Output Markdown file path (single file mode)")
    parser.add_argument("--output-dir", help="Output directory path (directory mode)")
    parser.add_argument("-r", "--recursive", action="store_true", help="Recursively search directory")
    parser.add_argument("-p", "--plugins", action="store_true", help="Enable 3rd-party plugins (e.g. markitdown-ocr)")

    args = parser.parse_args()
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: Path '{input_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    converter = MarkItDown(enable_plugins=args.plugins)

    if input_path.is_file():
        out_path = Path(args.output) if args.output else None
        ok = convert_single_file(converter, input_path, out_path)
        sys.exit(0 if ok else 1)
    elif input_path.is_dir():
        out_dir = Path(args.output_dir) if args.output_dir else (input_path / "markdown_output")
        convert_directory(converter, input_path, out_dir, recursive=args.recursive)
    else:
        print(f"Error: Invalid path '{input_path}'", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
