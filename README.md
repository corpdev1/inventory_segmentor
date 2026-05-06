# Inventory Segmenter MCP

An MCP server that takes a company data inventory spreadsheet and segments every row into one of seven buckets:

1. Product & Engineering
2. Customer & Sales
3. Strategy & Planning
4. Financial & Legal
5. Operations & HR
6. Marketing
7. Meeting Notes & Internal Comms

Classification happens inside the MCP server via the Anthropic API. The taxonomy and disambiguation rules live in `prompt.py` — edit that file to tune the classifier without touching the rest of the code.

## Project layout

```text
inventory-segmenter-mcp/
├── server.py        # MCP entry point — exposes the segment_inventory tool
├── segmenter.py     # Anthropic API call, batching, tool-use schema
├── excel_io.py      # Reads input, writes Master + 7 bucket sheets + Summary
├── prompt.py        # System prompt with the taxonomy (edit to tune)
├── pyproject.toml
└── README.md
```

## Install

```bash
cd inventory-segmenter-mcp
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -e .
```

## Configure

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Optional environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Which Claude model to use for classification |
| `SEGMENTER_BATCH_SIZE` | `25` | Rows per API call |

## Run as a standalone server

```bash
python server.py
```

The server speaks MCP over stdio. Most users will instead wire it into a client (below).

## Wire up to Claude Desktop

Add an entry to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "inventory-segmenter": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

Restart Claude Desktop. The `segment_inventory` tool will appear in the tools menu.

## Tool reference

```text
segment_inventory(
    input_path,
    output_path,
    sheet_name=None,
    description_column=None,
    source_column=None,
    model="claude-sonnet-4-6",
    batch_size=25,
) -> str
```

- `build_inventory_from_dump(dump_path, output_path, model="claude-sonnet-4-6", batch_size=25, max_files=None) -> str`
  - `dump_path` — absolute path to a folder containing the company’s “dump” (files + exports).
  - `output_path` — absolute path where the generated inventory `.xlsx` will be written.
  - Output workbook contains:
    - **Inventory** — 7 rows in the desired format (`Category`, `What it includes`, `Where to find it`, `How hard to pull`)
    - **Evidence** — one row per scanned artifact with bucket/confidence/rationale for auditability

- `input_path` — absolute path to a `.xlsx` or `.csv` data inventory.
- `output_path` — absolute path where the segmented workbook will be written.
- `sheet_name` — optional; defaults to the first sheet.
- `description_column` / `source_column` — optional overrides if auto-detection picks the wrong columns. The auto-detector recognises common header names like `Description`, `What it includes`, `Item`, `Source`, `Where to find it`, `System`, `Platform`.

The output workbook contains:

- **Master** — every input row plus `bucket_number`, `bucket_name`, `confidence`, `rationale`.
- **1. Product & Engineering** … **7. Meeting Notes & Internal Comms** — one sheet per bucket with just that bucket's rows.
- **Summary** — item counts and high/low confidence counts per bucket, with totals.

## How classification works

1. The server reads the input file with pandas and auto-detects the description and source columns (override via the tool args if needed).
2. Rows are batched — 25 per call by default — and sent to the Anthropic API as a JSON list.
3. The API call uses tool-use with `tool_choice` forced to `record_classifications`, so the response is always valid JSON matching the schema. No fragile parsing fallbacks.
4. Results are merged back by `row_id`. If a row is somehow missed, its bucket columns stay blank rather than getting silently dropped — easy to spot.

The system prompt in `prompt.py` includes disambiguation rules for source systems that span buckets (HubSpot for marketing vs CRM, DocuSign for legal vs sales, Carta for cap table vs investor data room, etc.). Items the model is unsure about come back with `confidence: "low"` and a rationale naming the alternative bucket so a human can review them.

## Tuning

- **Change the taxonomy** — edit `SEGMENTATION_SYSTEM_PROMPT` in `prompt.py`. The structured tool-use schema enforces seven buckets numbered 1–7; if you need a different count, also update `BUCKETS` in `excel_io.py` and the `bucket_number` constraint in `segmenter.py`'s `CLASSIFY_TOOL`.
- **Trade speed for cost** — set `ANTHROPIC_MODEL=claude-haiku-4-5-20251001` for cheaper, faster runs on large inventories. Set it to `claude-opus-4-7` if you want maximum classification quality.
- **Batch size** — larger batches = fewer API calls but more tokens per call. 25 is a good default; drop to 10 if rows have long descriptions, raise to 50 if they are very short.
