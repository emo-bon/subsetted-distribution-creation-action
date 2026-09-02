import io
from pathlib import Path
from unittest.mock import patch
from action.resource_loader import load_ena_qualifying_events, fetch_remote_resources

MOCK_ENA_CSV = """source_mat_id,ena_accession_number_run_metag,event_id,notes
EMOBON_BPNS_So_5,ERR13955095,BPNS_So_210726,replicate 1
EMOBON_BPNS_So_6,ERR13955096,BPNS_So_210726,replicate 2
EMOBON_BPNS_So_13,,BPNS_So_210825,no run accession
EMOBON_NRMCB_So_1,ERR13954860,NRMCB_So_210621,replicate 1
"""

def test_load_ena_qualifying_events():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = io.BytesIO(MOCK_ENA_CSV.encode("utf-8"))
        qualifying_events, mapping_rows = load_ena_qualifying_events("https://example.com/ena.csv")

    assert qualifying_events == {"BPNS_So_210726", "NRMCB_So_210621"}
    assert len(mapping_rows) == 3
    assert mapping_rows[0]["event_id"] == "BPNS_So_210726"
    assert mapping_rows[0]["ena_accession_number_run_metag"] == "ERR13955095"

def test_fetch_remote_resources(tmp_path: Path):
    yaml_input = """
    extra_table: "https://example.com/extra.csv"
    """
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = io.BytesIO(b"colA,colB\n1,2\n")
        resources = fetch_remote_resources(yaml_input, tmp_path)

    assert "extra_table" in resources
    assert resources["extra_table"].exists()
    assert resources["extra_table"].read_text() == "colA,colB\n1,2\n"
