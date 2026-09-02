# OpenAlex Publication Analysis Tools

This repository contains Python tools for analyzing academic publications using the [OpenAlex API](https://openalex.org/). It was developed as part of the participation in the **[SOAD 2026 hackathon](https://soad.ch/)**.

The project provides two main functionalities:
1. **EPFL Publications Export**: Fetches and exports publications linked to EPFL-affiliated researchers.
2. **Swiss Co-authors Checker**: Analyzes collaborations between a specific paper's authors and researchers at Swiss institutions across their entire publication history.

## Requirements

- Python 3.9+
- `pip`

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Tools and Usage

### 1. EPFL Publications Exporter

Queries the OpenAlex API and exports publications linked to EPFL-affiliated researchers into a CSV file.

```bash
python3 src/main.py
```

This creates `epfl_publications.csv` in the project folder.

#### Exporter Options

- `--output`: path to output CSV file (default: `epfl_publications.csv`)
- `--mailto`: contact email for OpenAlex polite pool
- `--api-key`: your OpenAlex API key
- `--limit`: maximum number of publications to export
- `--year`: only export publications from a specific publication year

**Example:**

```bash
python3 src/main.py \
  --output data/epfl_publications.csv \
  --mailto your.email@example.com \
  --api-key YOUR_OPENALEX_API_KEY \
  --limit 500 \
  --year 2024
```

### 2. Swiss Co-authors Checker (OpenAlex)

For all authors of a given starting publication, this tool checks their other works to find co-authors affiliated with Swiss institutions. It provides insights into collaboration patterns and shared research topics using OpenAlex data.

**Features:**
- Identifies Swiss-affiliated co-authors (country code "CH").
- Aggregates unique affiliations for each Swiss collaborator.
- Counts shared publications between the original team and Swiss researchers.
- Extracts and lists research topics for each collaborating pair.

**Usage:**

```bash
python3 src/check_swiss_coauthors.py --work-id W3146729407
```

#### Checker Options

- `--work-id`: OpenAlex ID of the starting publication (e.g., `W3146729407`).
- `--mailto`: contact email for OpenAlex polite pool.
- `--api-key`: your OpenAlex API key.

### 3. Swiss Co-authors Checker (OpenAIRE)

A version of the Swiss co-authors checker that uses the [OpenAIRE Graph API](https://graph.openaire.eu/).

**Usage:**

```bash
python3 src/check_swiss_coauthors_openaire.py --doi 10.7589/2019-08-202
```

#### OpenAIRE Options

- `--doi`: DOI of the starting publication (e.g., `10.7589/2019-08-202`).
- `--api-token`: your OpenAIRE Personal Access Token.

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

## Output Format

### CSV Export (Exporter)

The CSV contains:
- `id`, `doi`, `title`, `publication_year`, `type`, `cited_by_count`, `authorship_count`, `authors`.

### Summary Table (Checker)

The checker outputs a formatted table to the console:
- **Swiss Author**: Name of the Swiss-affiliated collaborator.
- **Total**: Total number of unique works shared with the original paper's author group.
- **Original Author**: The specific researcher from the starting paper.
- **Co-Works**: Number of publications shared between that specific pair.
- **Topics**: Research topics associated with their joint works.