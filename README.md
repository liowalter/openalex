# OpenAlex EPFL Publications Export

Small Python script that queries the OpenAlex API and exports publications linked to EPFL-affiliated researchers into a CSV file.

## Requirements

- Python 3.9+
- `pip`

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Run the exporter:

```bash
python3 src/main.py
```

This creates `epfl_publications.csv` in the project folder.

### Options

- `--output`: path to output CSV file (default: `epfl_publications.csv`)
- `--mailto`: contact email for OpenAlex polite pool
- `--api-key`: your OpenAlex API key
- `--limit`: maximum number of publications to export
- `--year`: only export publications from a specific publication year

Example with all options:

```bash
python3 src/main.py \
  --output data/epfl_publications.csv \
  --mailto your.email@example.com \
  --api-key YOUR_OPENALEX_API_KEY \
  --limit 500 \
  --year 2024
```

## Run tests

```bash
pytest -q
```

### Run the OpenAlex integration test

The integration test is opt-in and calls the real OpenAlex API.

```bash
OPENALEX_INTEGRATION=1 pytest -q
```

Optional environment variables:

- `OPENALEX_API_KEY`: API key for higher rate limits
- `OPENALEX_MAILTO`: contact email for polite pool access

## Output columns

The CSV contains:

- `id`
- `doi`
- `title`
- `publication_year`
- `type`
- `cited_by_count`
- `authorship_count`
- `authors`