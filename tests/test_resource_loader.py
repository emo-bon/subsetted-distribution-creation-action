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

SAMPLE_OBSERVATORIES_CSV = """country_code,country,EMOBON_observatory_name,EMOBON_observatory_id,organization,organization_edmoid,startdate,enddate,Water_Column,Soft_Substrates,Hard_Substrates,water_site_latitude,water_site_longitude,sediment_site_latitude,sediment_site_longtitude,hard_substrates_site1_longitude,hard_substrates_site1_latitude,hard_substrates_site2_longtitude,hard_substrates_site2_latitude,contact_person,contact_person_email,ENA_accession_number_umbrella,ENA_accession_number_project,EMOBON_core,loc_broad_ocean,loc_regional,loc_loc
BE,Belgium,EMOBON-BE,BPNS,Flanders Marine Institute (VLIZ),422,6/1/2021,,y,y,y,51.433331,2.808331,51.433331,2.80833,51.579997,2.9933,NaN,NaN,Klaas Deneudt,klaas.deneudt@vliz.be,PRJEB51688,PRJEB51652,y,North Atlantic Ocean,North Sea,Belgian part of the North Sea
FR,France,Bay of Villefranche sur Mer- southern France,VB,Institut de la Mer de Villefranche,5041,6/1/2021,,y,n,y,43.683,7.317,NaN,NaN,43.674619,7.332372,NaN,NaN,Cecile Fauvelot,cecile.fauvelot@ird.fr,PRJEB51688,PRJEB51664,y,Mediterranean Sea - Western Basin,Villefranche Bay,Villefranche Bay - Point B
"""

def test_load_observatories_governance(tmp_path: Path):
    from action.resource_loader import load_observatories_governance
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = io.BytesIO(SAMPLE_OBSERVATORIES_CSV.encode("utf-8"))
        mapping = load_observatories_governance("https://example.com/observatories.csv", cache_dir=tmp_path)

        assert "BPNS" in mapping
        assert mapping["BPNS"]["observatory_name"] == "EMOBON-BE"
        assert mapping["BPNS"]["country"] == "Belgium"
        assert mapping["BPNS"]["water_site_latitude"] == "51.433331"
        assert mapping["BPNS"]["water_site_longitude"] == "2.808331"

        assert "VB" in mapping
        assert mapping["VB"]["observatory_name"] == "Bay of Villefranche sur Mer- southern France"
        assert mapping["VB"]["country"] == "France"

def test_load_observatories_governance_fallback(tmp_path: Path):
    from action.resource_loader import load_observatories_governance
    with patch("urllib.request.urlopen", side_effect=Exception("Network error")):
        mapping = load_observatories_governance("https://example.com/unreachable.csv", cache_dir=tmp_path)
        assert mapping == {}

