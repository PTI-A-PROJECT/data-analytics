---
name: markitdown
description: Convert various file formats (PDF, Word DOCX, PowerPoint PPTX, Excel XLSX, HTML, images, audio, CSV, JSON, XML, ZIP, EPUB, YouTube URLs) into clean, LLM-ready Markdown using Microsoft MarkItDown. Use when asked to convert documents to markdown, extract structured text or tables from office files/PDFs, or prepare files for text analysis and LLM workflows.
---

# Microsoft MarkItDown Skill

Convert heterogeneous documents and files into clean, structured, LLM-friendly Markdown using [Microsoft MarkItDown](https://github.com/microsoft/markitdown).

MarkItDown is designed specifically for LLM pipelines and text analysis, preserving document hierarchy (headings, bulleted/numbered lists, tables, links, code blocks) with high token efficiency.

---

## Supported File Formats

Format / Extension        | Capabilities & Extracted Content
:------------------------ | :--------------------------------------------------------------
**PDF** (`.pdf`)          | Text, layout hierarchy, tables, multi-page document structure
**Word** (`.docx`)        | Headings, paragraphs, tables, lists, text formatting
**PowerPoint** (`.pptx`)  | Slide titles, slide body text, speaker notes, shapes
**Excel** (`.xlsx`, `.xls`)| Worksheets converted directly to formatted Markdown tables
**HTML** (`.html`, `.htm`)| Clean Markdown structure via BeautifulSoup & Markdownify
**Text** (`.csv`, `.json`, `.xml`)| Tabular and structured data formatted as Markdown
**Audio** (`.wav`, `.mp3`)| Speech transcription (via SpeechRecognition) and EXIF metadata
**Images** (`.jpg`, `.png`, `.tiff`)| EXIF metadata inspection; OCR if plugins are configured
**Archives** (`.zip`)     | Iterates through and converts all supported files in archive
**Web / Video** (YouTube) | Automatically extracts transcripts from YouTube URLs

---

## Quick Execution Commands

### 1. Command-Line Interface (CLI)

Run via Python module to avoid PATH lookup issues:

```powershell
# Convert a file and print directly to terminal
python -m markitdown "path/to/document.pdf"

# Convert and save output to a Markdown file
python -m markitdown "path/to/document.pdf" -o "output.md"

# Convert Excel spreadsheet to Markdown tables
python -m markitdown "data/report.xlsx" -o "report.md"

# Convert PowerPoint slides to Markdown
python -m markitdown "presentation.pptx" -o "presentation.md"

# Piping / STDIN conversion (specify extension hint when piping)
Get-Content "document.pdf" -Raw | python -m markitdown -x pdf -o "document.md"
```

### 2. Batch Conversion via Built-in Helper Script

Use the helper script included in this skill:

```powershell
# Convert a single file
python scripts/convert.py --input "path/to/document.docx" --output "output.md"

# Convert an entire folder of mixed files (PDF, DOCX, XLSX, etc.)
python scripts/convert.py --input "documents_folder/" --output-dir "markdown_output/" --recursive
```

### 3. Python API Integration

For programmatic conversion within scripts:

```python
from markitdown import MarkItDown

# Initialize converter
md = MarkItDown()

# Convert file
result = md.convert("financial_report.xlsx")

# Access Markdown content
markdown_text = result.text_content
print(markdown_text)

# Save to file
with open("financial_report.md", "w", encoding="utf-8") as f:
    f.write(markdown_text)
```

---

## Advanced Options

### Cloud Enhancements (Azure AI)
If Azure Document Intelligence or Azure Content Understanding is available:

```powershell
# Using Document Intelligence endpoint
python -m markitdown "document.pdf" --use-docintel --endpoint "https://<your-service>.cognitiveservices.azure.com/"

# Using Azure Content Understanding
python -m markitdown "document.pdf" --use-cu --cu-endpoint "https://<your-endpoint>"
```

### Plugins and OCR
To list or enable 3rd-party plugins:

```powershell
# List available plugins
python -m markitdown --list-plugins

# Run with plugins enabled (e.g., markitdown-ocr)
python -m markitdown --use-plugins "scanned_doc.pdf" -o "scanned_doc.md"
```

---

## Best Practices & Guidelines for the Agent

1. **Output File Placement**: Save converted Markdown files in the same directory as the source file or in an `output/` or `markdown/` subfolder.
2. **UTF-8 Encoding**: Always ensure markdown files are written with UTF-8 encoding (`encoding="utf-8"` in Python or `-Encoding utf8` in PowerShell).
3. **Preserving Structure**: For tabular data (Excel, CSV, DB dumps), inspect the converted Markdown tables to confirm column alignments before feeding them into LLM contexts.
4. **Token Economy**: For very large files (e.g. 100+ page PDFs or massive Excel sheets), consider converting specific pages or sheets if full conversion produces excessive tokens.

---

## Detailed Documentation
- [Python API Reference](references/api-reference.md)
- [Supported Formats Matrix](references/supported-formats.md)
