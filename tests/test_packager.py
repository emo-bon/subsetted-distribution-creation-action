import zipfile
from pathlib import Path
from action.packager import package_subset_archive

def test_package_subset_archive(tmp_path: Path):
    stage_dir = tmp_path / "stage"
    stage_dir.mkdir()
    (stage_dir / "logsheets").mkdir()
    (stage_dir / "logsheets" / "sediment_sampling.csv").write_text("dummy,data\n1,2\n")
    (stage_dir / "all-triples.ttl").write_text("@prefix ex: <http://example.org/> .\n")
    (stage_dir / "ro-crate-metadata.json").write_text('{"@context": "https://w3id.org/ro/crate/1.2/context"}')

    mapping = [{"event_id": "EV1", "source_mat_id": "SM1", "ena_accession_number_run_metag": "ERR123"}]

    citation = "EMO BON Consortium (2026). EMO BON BPNS Subsetted Distribution."
    zip_path = package_subset_archive(stage_dir, "BPNS", "bluecloud-ENA", mapping, citation_text=citation)

    assert zip_path.exists()
    assert zip_path.name == "BPNS_bluecloud-ENA.zip"

    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert "logsheets/sediment_sampling.csv" in namelist
        assert "all-triples.ttl" in namelist
        assert "ena_accessions_subset.csv" in namelist
        assert "ro-crate-metadata.json" in namelist
        assert "README.md" in namelist

        readme = zf.read("README.md").decode("utf-8")
        assert "## Citation" in readme
        assert citation in readme
        assert "RO-Crate 1.2" in readme

