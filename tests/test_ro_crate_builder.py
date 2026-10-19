import json
from pathlib import Path
from action.ro_crate_builder import build_ro_crate

def test_build_ro_crate(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True)
    (output_dir / "all-triples.ttl").write_text("", encoding="utf-8")
    (output_dir / "ena_accessions_subset.csv").write_text("event_id\n", encoding="utf-8")
    (output_dir / "README.md").write_text("# Test\n", encoding="utf-8")

    metadata = {
        "title": "Marine genomic sampling metadata from EMO BON Observation Network [station EMOBON-BE; Belgium]",
        "description": "Here you will find all the data collected...",
        "date_published": "2026-10-19",
        "date_modified": "2026-10-19",
        "temporal_coverage": "2021-06-01/2022-09-15",
        "start_date": "2021-06-01",
        "end_date": "2022-09-15",
        "geo_bbox": "51.2 2.8 51.6 3.1",
        "observatory_name": "EMOBON-BE",
        "country": "Belgium",
        "repo_landing_url": "https://data.emobon.embrc.eu/observatory-bpns-crate/",
        "release_tag_url": "https://github.com/emo-bon/observatory-bpns-crate/releases/tag/bluecloud-ENA-latest",
        "citation_text": "European Marine Biological Research Centre...",
        "parameters": [
            {"name": "silicate", "property_id": "http://vocab.nerc.ac.uk/collection/P01/current/SLCAAA01/"}
        ],
        "instruments": ["Colorimetry"],
        "organizations": [
            {"name": "Flanders Marine Institute (VLIZ)", "edmo_url": "https://edmo.seadatanet.org/report/422"}
        ],
        "active_habitats": ["water"],
    }

    crate_json_path = build_ro_crate(output_dir, metadata)

    assert crate_json_path.exists()
    assert crate_json_path.name == "ro-crate-metadata.json"

    with open(crate_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "@graph" in data
    graph_by_id = {node["@id"]: node for node in data["@graph"]}

    assert "./" in graph_by_id
    root_dataset = graph_by_id["./"]
    assert root_dataset["name"] == metadata["title"]
    assert root_dataset["license"] == "https://creativecommons.org/licenses/by/4.0/"
    assert root_dataset["temporalCoverage"] == "2021-06-01/2022-09-15"
    assert "EMOBON-BE" in root_dataset["keywords"]
    assert "Biota" in root_dataset["keywords"]

    # Organization node exists
    assert "https://edmo.seadatanet.org/report/422" in graph_by_id
    org_node = graph_by_id["https://edmo.seadatanet.org/report/422"]
    assert org_node["name"] == "Flanders Marine Institute (VLIZ)"

def test_build_ro_crate_fallback(tmp_path, monkeypatch):
    import action.ro_crate_builder as builder
    monkeypatch.setattr(builder, "ROCreator", None)

    output_dir = tmp_path / "output_fallback"
    output_dir.mkdir(parents=True)

    metadata = {
        "title": "Marine genomic sampling metadata from EMO BON Observation Network [station EMOBON-BE; Belgium]",
        "description": "Here you will find all the data collected...",
        "date_published": "2026-10-19",
        "date_modified": "2026-10-19",
        "temporal_coverage": "2021-06-01/2022-09-15",
        "start_date": "2021-06-01",
        "end_date": "2022-09-15",
        "geo_bbox": "51.2 2.8 51.6 3.1",
        "observatory_name": "EMOBON-BE",
        "country": "Belgium",
        "repo_landing_url": "https://data.emobon.embrc.eu/observatory-bpns-crate/",
        "release_tag_url": "https://github.com/emo-bon/observatory-bpns-crate/releases/tag/bluecloud-ENA-latest",
        "citation_text": "European Marine Biological Research Centre...",
        "parameters": [
            {"name": "silicate", "property_id": "http://vocab.nerc.ac.uk/collection/P01/current/SLCAAA01/"}
        ],
        "instruments": ["Colorimetry"],
        "organizations": [
            {"name": "Flanders Marine Institute (VLIZ)", "edmo_url": "https://edmo.seadatanet.org/report/422"}
        ],
        "active_habitats": ["water"],
    }

    crate_json_path = builder.build_ro_crate(output_dir, metadata)
    assert crate_json_path.exists()
    with open(crate_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "@graph" in data

