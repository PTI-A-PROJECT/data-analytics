# MarkItDown Python API Reference

This reference covers the Python API for Microsoft `markitdown`.

## Core Class: `MarkItDown`

```python
from markitdown import MarkItDown

md = MarkItDown(
    enable_plugins=False,
    llm_client=None,
    llm_model=None,
    docintel_endpoint=None,
    content_understanding_endpoint=None
)
```

### Parameters

- `enable_plugins` (*bool*, optional): Enables dynamic loading of 3rd-party plugins registered under the `markitdown.plugin` entrypoint (e.g. `markitdown-ocr`). Default: `False`.
- `llm_client` (*object*, optional): OpenAI or compatible client instance used for vision-based image descriptions or OCR plugins.
- `llm_model` (*str*, optional): Model identifier (e.g. `"gpt-4o"`) passed to `llm_client`.
- `docintel_endpoint` (*str*, optional): Azure Document Intelligence endpoint URL.
- `content_understanding_endpoint` (*str*, optional): Azure Content Understanding endpoint URL.

---

## Methods

### `convert(source, **kwargs) -> DocumentConverterResult`

Converts a local file path, URL, or stream to Markdown.

```python
result = md.convert("document.pdf")
print(result.text_content)
```

#### Returns:
`DocumentConverterResult` object containing:
- `text_content` (*str*): The resulting Markdown text content.
- `title` (*str*, optional): Extracted document title if found.

### `convert_stream(stream, file_extension=None, **kwargs) -> DocumentConverterResult`

Converts an open binary stream directly:

```python
with open("data.xlsx", "rb") as f:
    result = md.convert_stream(f, file_extension=".xlsx")
    print(result.text_content)
```

---

## CLI Options

```text
usage: markitdown [-h] [-v] [-o OUTPUT] [-x EXTENSION] [-m MIME_TYPE]
                  [-c CHARSET] [-d] [--use-cu] [-e ENDPOINT]
                  [--cu-endpoint CU_ENDPOINT] [--cu-analyzer CU_ANALYZER]
                  [--cu-file-types CU_FILE_TYPES] [-p] [--list-plugins]
                  [--keep-data-uris]
                  [filename]
```

Option                      | Description
:-------------------------- | :------------------------------------------------------
`-o, --output <file>`       | Write converted output to specified file
`-x, --extension <ext>`     | Provide extension hint (useful when reading from stdin)
`-p, --use-plugins`         | Enable 3rd-party plugins
`--list-plugins`            | List all installed 3rd-party plugins
`-d, --use-docintel`        | Use Azure Document Intelligence
`--use-cu`                  | Use Azure Content Understanding
`--keep-data-uris`          | Keep embedded base64 image URIs in markdown
