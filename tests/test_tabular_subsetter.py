from pathlib import Path
from action.tabular_subsetter import subset_logsheets

def test_subset_logsheets(tmp_path: Path):
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "output"
    logsheets_dir = workspace / "logsheets" / "transformed"
    logsheets_dir.mkdir(parents=True)

    # Mock sampling.csv
    sampling_csv = logsheets_dir / "sediment_sampling.csv"
    sampling_csv.write_text(
        "source_mat_id_orig,source_mat_id,sampling_event,tax_id\n"
        "ORIG_1,EMOBON_1,EVENT_A,33208\n"
        "ORIG_2,EMOBON_2,EVENT_A,33208\n"
        "ORIG_3,EMOBON_3,EVENT_B,33208\n"
    )

    # Mock measured.csv
    measured_csv = logsheets_dir / "sediment_measured.csv"
    measured_csv.write_text(
        "source_mat_id_orig,source_mat_id,ph,temp\n"
        "ORIG_1,EMOBON_1,7.5,14.2\n"
        "ORIG_2,EMOBON_2,7.4,14.1\n"
        "ORIG_3,EMOBON_3,8.0,15.0\n"
    )

    # Mock observatory.csv
    obs_csv = logsheets_dir / "sediment_observatory.csv"
    obs_csv.write_text("project_name,latitude,longitude\nBPNS,51.2,3.1\n")

    events_count, samples_count, sample_ids = subset_logsheets(workspace, out_dir, {"EVENT_A"})

    assert events_count == 1
    assert samples_count == 2
    assert sample_ids == {"EMOBON_1", "EMOBON_2", "ORIG_1", "ORIG_2"}

    # Verify generated output files
    out_sampling = out_dir / "logsheets" / "sediment_sampling.csv"
    out_measured = out_dir / "logsheets" / "sediment_measured.csv"
    out_obs = out_dir / "logsheets" / "sediment_observatory.csv"

    assert out_sampling.exists()
    assert out_measured.exists()
    assert out_obs.exists()

    sampling_lines = out_sampling.read_text().strip().splitlines()
    assert len(sampling_lines) == 3  # header + 2 rows for EVENT_A
    assert "EVENT_B" not in out_sampling.read_text()

    measured_lines = out_measured.read_text().strip().splitlines()
    assert len(measured_lines) == 3  # header + 2 rows for EMOBON_1 & EMOBON_2
    assert "EMOBON_3" not in out_measured.read_text()
