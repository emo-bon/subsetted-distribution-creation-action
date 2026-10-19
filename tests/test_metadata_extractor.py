from pathlib import Path
import pytest
from rdflib import Graph, Literal, Namespace, RDF, URIRef
from action.metadata_extractor import (
    extract_distribution_metadata,
    generate_description_text,
    format_habitat_list,
)

SOSA = Namespace("http://www.w3.org/ns/sosa/")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
DCTERMS = Namespace("http://purl.org/dc/terms/")
SCHEMA = Namespace("https://schema.org/")

def test_format_habitat_list():
    assert format_habitat_list(["water"]) == "water"
    assert format_habitat_list(["water", "sediment"]) == "water, sediment"
    assert format_habitat_list(["water", "sediment", "hard"]) == "water, sediment, and hard-bottom"
    assert format_habitat_list(["hard"]) == "hard-bottom"

def test_generate_description_text():
    desc = generate_description_text("EMOBON-BE", ["water", "sediment"])
    assert "observatory EMOBON-BE for their water, sediment sampling activities." in desc
    assert "PRJEB51688" in desc

def test_extract_distribution_metadata(tmp_path):
    output_dir = tmp_path / "output"
    logsheets_dir = output_dir / "logsheets"
    logsheets_dir.mkdir(parents=True)

    # 1. Mock water_sampling.csv
    water_sampling = logsheets_dir / "water_sampling.csv"
    water_sampling.write_text(
        "sampling_event,event_date,decimalLatitude,decimalLongitude\n"
        "EV01,2021-06-01,51.2,2.8\n"
        "EV02,2022-09-15,51.6,3.1\n",
        encoding="utf-8"
    )

    # 2. Mock water_observatory.csv
    water_obs = logsheets_dir / "water_observatory.csv"
    water_obs.write_text(
        "observatory_id,organization,organization_edmoid\n"
        "BPNS,Flanders Marine Institute (VLIZ);Ghent University,422;449\n",
        encoding="utf-8"
    )

    # 3. Mock all-triples.ttl with observations
    ttl_file = output_dir / "all-triples.ttl"
    g = Graph()
    obs_uri = URIRef("https://data.emobon.embrc.eu/obs/1")
    g.add((obs_uri, RDF.type, SOSA.Observation))
    g.add((obs_uri, RDFS.label, Literal("silicate")))
    g.add((obs_uri, DCTERMS.identifier, URIRef("http://vocab.nerc.ac.uk/collection/P01/current/SLCAAA01/")))
    g.add((obs_uri, SCHEMA.measurementTechnique, Literal("Colorimetry")))
    g.serialize(ttl_file, format="turtle")

    governance = {
        "BPNS": {
            "observatory_name": "EMOBON-BE",
            "country": "Belgium",
            "water_site_latitude": "51.4",
            "water_site_longitude": "2.8"
        }
    }

    metadata = extract_distribution_metadata(
        workspace_dir=tmp_path,
        output_dir=output_dir,
        observatory_id="BPNS",
        governance_mapping=governance,
        repo_name="emo-bon/observatory-bpns-crate",
        distribution_affix="bluecloud-ENA"
    )

    assert metadata["observatory_name"] == "EMOBON-BE"
    assert metadata["country"] == "Belgium"
    assert metadata["title"] == "Marine genomic sampling metadata from EMO BON Observation Network [station EMOBON-BE; Belgium]"
    assert metadata["temporal_coverage"] == "2021-06-01/2022-09-15"
    assert metadata["geo_bbox"] == "51.2 2.8 51.6 3.1"
    assert len(metadata["parameters"]) == 1
    assert metadata["parameters"][0]["name"] == "silicate"
    assert metadata["parameters"][0]["property_id"] == "http://vocab.nerc.ac.uk/collection/P01/current/SLCAAA01/"
    assert "Colorimetry" in metadata["instruments"]
    assert len(metadata["organizations"]) == 2
    assert metadata["organizations"][0]["name"] == "Flanders Marine Institute (VLIZ)"
    assert metadata["organizations"][0]["edmo_url"] == "https://edmo.seadatanet.org/report/422"
