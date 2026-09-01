import argparse
import csv
from typing import Any, Dict, Iterable, List, Optional

import requests

OPENALEX_BASE_URL = "https://api.openalex.org"


def openalex_get(endpoint: str, params: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    request_params = dict(params)
    if api_key:
        request_params["api_key"] = api_key

    response = requests.get(
        f"{OPENALEX_BASE_URL}/{endpoint}",
        params=request_params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def find_epfl_institution_id(mailto: Optional[str] = None, api_key: Optional[str] = None) -> str:
    params: Dict[str, Any] = {
        "search": "EPFL",
        "per-page": 25,
    }
    if mailto:
        params["mailto"] = mailto

    data = openalex_get("institutions", params, api_key=api_key)
    results = data.get("results", [])
    if not results:
        raise RuntimeError("No institution found for EPFL")

    preferred_names = {
        "École Polytechnique Fédérale de Lausanne",
        "Ecole Polytechnique Federale de Lausanne",
        "EPFL",
    }

    for institution in results:
        if institution.get("display_name") in preferred_names:
            return institution["id"]

    return results[0]["id"]


def iter_works_for_institution(
    institution_id: str,
    mailto: Optional[str] = None,
    api_key: Optional[str] = None,
    year: Optional[int] = None,
) -> Iterable[Dict[str, Any]]:
    cursor = "*"
    while True:
        filter_parts = [f"authorships.institutions.id:{institution_id}"]
        if year is not None:
            filter_parts.append(f"publication_year:{year}")

        params: Dict[str, Any] = {
            "filter": ",".join(filter_parts),
            "per-page": 200,
            "cursor": cursor,
        }
        if mailto:
            params["mailto"] = mailto

        data = openalex_get("works", params, api_key=api_key)
        results: List[Dict[str, Any]] = data.get("results", [])
        for work in results:
            yield work

        next_cursor = data.get("meta", {}).get("next_cursor")
        if not results or not next_cursor:
            break
        cursor = next_cursor


def work_to_row(work: Dict[str, Any]) -> Dict[str, Any]:
    authors = [a.get("author", {}).get("display_name", "") for a in work.get("authorships", [])]
    return {
        "id": work.get("id", ""),
        "doi": work.get("doi", ""),
        "title": work.get("display_name", ""),
        "publication_year": work.get("publication_year", ""),
        "type": work.get("type", ""),
        "cited_by_count": work.get("cited_by_count", 0),
        "authorship_count": len(work.get("authorships", [])),
        "authors": "; ".join(a for a in authors if a),
    }


def export_publications(
    output_csv: str,
    mailto: Optional[str] = None,
    api_key: Optional[str] = None,
    limit: Optional[int] = None,
    year: Optional[int] = None,
) -> None:
    institution_id = find_epfl_institution_id(mailto=mailto, api_key=api_key)
    fieldnames = [
        "id",
        "doi",
        "title",
        "publication_year",
        "type",
        "cited_by_count",
        "authorship_count",
        "authors",
    ]

    with open(output_csv, "w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()

        count = 0
        for work in iter_works_for_institution(
            institution_id,
            mailto=mailto,
            api_key=api_key,
            year=year,
        ):
            if limit is not None and count >= limit:
                break
            writer.writerow(work_to_row(work))
            count += 1

    print(f"Exported {count} publications for institution {institution_id} to {output_csv}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch publications for EPFL-affiliated researchers from OpenAlex and write to CSV.",
    )
    parser.add_argument(
        "--output",
        default="epfl_publications.csv",
        help="Path to output CSV file (default: epfl_publications.csv)",
    )
    parser.add_argument(
        "--mailto",
        default=None,
        help="Contact email passed to OpenAlex for polite pool access.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenAlex API key.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of publications to export.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Only export publications from this year.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    export_publications(
        output_csv=args.output,
        mailto=args.mailto,
        api_key=args.api_key,
        limit=args.limit,
        year=args.year,
    )
