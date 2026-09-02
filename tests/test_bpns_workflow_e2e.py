import urllib.request
import zipfile
from pathlib import Path
import rdflib
from action.main import run_pipeline

def test_bpns_real_workflow_integration(tmp_path: Path):
    workspace = tmp_path / "observatory-bpns-crate"
    output_dir = tmp_path / "subsetted_distribution"
    logsheets_dir = workspace / "logsheets" / "transformed"
    logsheets_dir.mkdir(parents=True)

    base_url = "https://raw.githubusercontent.com/emo-bon/observatory-bpns-crate/main"
    for filename in ["sediment_sampling.csv", "sediment_measured.csv", "sediment_observatory.csv",
                     "water_sampling.csv", "water_measured.csv", "water_observatory.csv"]:
        try:
            req = urllib.request.Request(f"{base_url}/logsheets/transformed/{filename}", headers={"User-Agent": "curl"})
            content = urllib.request.urlopen(req, timeout=30).read()
            (logsheets_dir / filename).write_bytes(content)
        except Exception as e:
            print(f"Skipping {filename}: {e}")

    # Fetch real all-triples.ttl
    req = urllib.request.Request(f"{base_url}/all-triples.ttl", headers={"User-Agent": "curl"})
    ttl_content = urllib.request.urlopen(req, timeout=60).read()
    (workspace / "all-triples.ttl").write_bytes(ttl_content)

    ena_url = "https://raw.githubusercontent.com/emo-bon/sequencing-logistics-crate/main/ena-accession-numbers-batches1-2.csv"

    outputs = run_pipeline(
        workspace_dir=workspace,
        output_dir=output_dir,
        ena_records_url=ena_url,
        remote_resources="",
        distribution_affix="bluecloud-ENA",
        repo_name="emo-bon/observatory-bpns-crate",
        token="",
        create_release=False
    )

    assert outputs["subsetted_events_count"] > 0
    assert outputs["release_tag"] == "bluecloud-ENA-latest"

    zip_file = output_dir / "BPNS_bluecloud-ENA.zip"
    assert zip_file.exists()

    with zipfile.ZipFile(zip_file, "r") as zf:
        namelist = zf.namelist()
        assert "all-triples.ttl" in namelist
        assert "ena_accessions_subset.csv" in namelist
        assert "README.md" in namelist
        assert "logsheets/sediment_sampling.csv" in namelist

    # Verify distribution was linked in root all-triples.ttl
    root_g = rdflib.Graph()
    root_g.parse(workspace / "all-triples.ttl", format="turtle")
    dist_uri = rdflib.URIRef("https://data.emobon.embrc.eu/observatory-bpns-crate/distribution/bluecloud-ENA")
    assert (dist_uri, rdflib.RDF.type, rdflib.URIRef("http://www.w3.org/ns/dcat#Distribution")) in root_g
    assert (dist_uri, rdflib.RDF.type, rdflib.URIRef("https://schema.org/DataDownload")) in root_g
