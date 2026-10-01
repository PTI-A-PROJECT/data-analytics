# MarkItDown Supported Formats Matrix

Microsoft MarkItDown supports converting multiple document, tabular, media, and archive formats into Markdown.

## Document Formats

### PDF (`.pdf`)
- Powered by `pdfminer.six` and `pypdfium2`.
- Extracts headings, body paragraphs, text coordinates, table structures, and page separations.

### Word Documents (`.docx`, `.doc`)
- Powered by `mammoth` and `python-docx`.
- Extracts styled headings (H1, H2, H3), paragraphs, bulleted and numbered lists, inline emphasis (bold, italic), hyperlinks, and tables.

### PowerPoint Presentations (`.pptx`, `.ppt`)
- Powered by `python-pptx`.
- Converts slides in sequence, including slide headings, bullet points, text boxes, tables, and speaker presentation notes.

---

## Tabular Formats

### Excel Workbooks (`.xlsx`, `.xls`)
- Powered by `openpyxl` and `xlrd`.
- Formats each worksheet into clean GitHub-flavored Markdown tables.

### CSV & TSV (`.csv`, `.tsv`)
- Parsed and converted to aligned Markdown tables.

---

## Web & Structured Data

### HTML (`.html`, `.htm`)
- Powered by `BeautifulSoup4` and `markdownify`.
- Cleans up scripts, styles, and unwanted markup while converting DOM structure to Markdown.

### JSON & XML (`.json`, `.xml`)
- Converts structured data trees into formatted, readable Markdown code blocks and sections.

### YouTube URLs
- Powered by `youtube-transcript-api`.
- Fetches video captions/transcripts automatically from public YouTube URLs.

---

## Multimedia

### Audio (`.wav`, `.mp3`)
- Powered by `SpeechRecognition` and `pydub`.
- Generates speech transcription into Markdown.

### Images (`.jpg`, `.jpeg`, `.png`, `.tiff`)
- Powered by `Pillow`.
- Extracts EXIF metadata (camera model, timestamps, GPS, dimensions).
- Can perform OCR when `markitdown-ocr` plugin or vision client is configured.

---

## Archives

### ZIP Files (`.zip`)
- Recursively unpacks and converts all supported files contained within the archive into unified Markdown sections.
