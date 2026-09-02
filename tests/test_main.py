from pathlib import Path
from unittest.mock import patch
from action.main import run_pipeline

def test_run_pipeline(tmp_path: Path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    logsheets = workspace / "logsheets" / "transformed"
    logsheets.mkdir(parents=True)

    (logsheets / "sediment_sampling.csv").write_text("source_mat_id_orig,source_mat_id,sampling_event\nORIG_1,EMOBON_1,EV1\n")
    (logsheets / "sediment_measured.csv").write_text("source_mat_id_orig,source_mat_id,temp\nORIG_1,EMOBON_1,15\n")
    (logsheets / "sediment_observatory.csv").write_text("station\nBPNS\n")
    (workspace / "all-triples.ttl").write_text("@prefix sosa: <http://www.w3.org/ns/sosa/> .\n<http://ex.org/EV1> a sosa:Sampling .\n")

    with patch("action.main.load_ena_qualifying_events", return_value=({"EV1"}, [{"event_id": "EV1", "source_mat_id": "EMOBON_1", "ena_accession_number_run_metag": "ERR1"}])):
        outputs = run_pipeline(
            workspace_dir=workspace,
            output_dir=tmp_path / "out",
            ena_records_url="https://dummy.url",
            remote_resources="",
            distribution_affix="bluecloud-ENA",
            repo_name="emo-bon/observatory-bpns-crate",
            token="",
            create_release=False
        )

    assert outputs["subsetted_events_count"] == 1
    assert outputs["release_tag"] == "bluecloud-ENA-latest"
    assert "BPNS_bluecloud-ENA.zip" in outputs["release_download_url"]
