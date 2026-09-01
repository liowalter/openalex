import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import main


def test_parse_args_accepts_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--api-key",
            "test-key",
            "--output",
            "out.csv",
            "--limit",
            "10",
            "--year",
            "2024",
        ],
    )
    args = main.parse_args()

    assert args.api_key == "test-key"
    assert args.output == "out.csv"
    assert args.limit == 10
    assert args.year == 2024


def test_openalex_get_forwards_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_get = MagicMock()
    response = MagicMock()
    response.json.return_value = {"results": []}
    response.raise_for_status.return_value = None
    mock_get.return_value = response
    monkeypatch.setattr(main.requests, "get", mock_get)

    main.openalex_get("works", {"search": "EPFL"}, api_key="secret")

    _, kwargs = mock_get.call_args
    assert kwargs["params"]["api_key"] == "secret"
    assert kwargs["params"]["search"] == "EPFL"


def test_export_publications_applies_limit_and_year(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mock_find_epfl_institution_id = MagicMock(return_value="I-EPFL")
    mock_iter_works_for_institution = MagicMock(
        return_value=iter(
            [
                {
                    "id": f"W{i}",
                    "doi": "",
                    "display_name": f"Title {i}",
                    "publication_year": 2024,
                    "type": "article",
                    "cited_by_count": i,
                    "authorships": [],
                }
                for i in range(3)
            ]
        )
    )
    monkeypatch.setattr(main, "find_epfl_institution_id", mock_find_epfl_institution_id)
    monkeypatch.setattr(main, "iter_works_for_institution", mock_iter_works_for_institution)

    output_path = tmp_path / "test_output.csv"
    monkeypatch.setattr("builtins.print", MagicMock())
    main.export_publications(str(output_path), limit=2, year=2024)

    rows = output_path.read_text(encoding="utf-8").strip().splitlines()

    mock_find_epfl_institution_id.assert_called_once_with(mailto=None, api_key=None)
    mock_iter_works_for_institution.assert_called_once_with(
        "I-EPFL",
        mailto=None,
        api_key=None,
        year=2024,
    )

    # header + 2 rows
    assert len(rows) == 3


def test_integration_openalex_epfl_lookup_and_works() -> None:
    if os.getenv("OPENALEX_INTEGRATION") != "1":
        pytest.skip("Set OPENALEX_INTEGRATION=1 to run OpenAlex integration test")

    mailto = os.getenv("OPENALEX_MAILTO")
    api_key = os.getenv("OPENALEX_API_KEY")

    institution_id = main.find_epfl_institution_id(mailto=mailto, api_key=api_key)
    assert institution_id
    assert "I" in institution_id

    first_work = next(
        main.iter_works_for_institution(
            institution_id,
            mailto=mailto,
            api_key=api_key,
        ),
        None,
    )
    assert first_work is not None
    assert "id" in first_work
    assert "display_name" in first_work
    assert "publication_year" in first_work
    assert "authorships" in first_work