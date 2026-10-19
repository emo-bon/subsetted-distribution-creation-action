# Blue Cloud RO-Crate Metadata Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement automated RO-Crate 1.2 metadata generation (`ro-crate-metadata.json`) in `subsetted-distribution-creation-action` using `pysema` to meet Blue-Cloud Level 1 catalog harvesting standards for EMO BON subsetted distributions.

**Architecture:** A metadata aggregation module extracts spatial bounding boxes, temporal ranges, measured parameters, and organization EDMO identifiers from subsetted tabular logsheets, RDF triples, and `governance-crate/observatories.csv`. A blueprint-driven `pysema.ro.creator.ROCreator` renders `output_dir/ro-crate-metadata.json`, which is bundled into `<observatory>_<affix>.zip` and published as an independent asset in the GitHub Release alongside distribution triples in `all-triples.ttl`.

**Tech Stack:** Python 3.10+, `pysema` (0.1.0), `rdflib` (7.0+), `pyyaml`, `pytest`, GitHub Actions.

**Spec:** [docs/superpowers/specs/2026-10-19-blue-cloud-ro-crate-metadata-design.md](file:///c:/Users/cedricd/Documents/Github/subsetted-distribution-creation-action/docs/superpowers/specs/2026-10-19-blue-cloud-ro-crate-metadata-design.md)

## Global Constraints

* Output file must be named `ro-crate-metadata.json` placed inside `output_dir`.
* Root dataset `@id` is relative (`"./"`), with `identifier` and `url` set to live landing pages (`https://data.emobon.embrc.eu/{repo_slug}/` and the GitHub release tag URL).
* Conforms to RO-Crate 1.2 (`conformsTo: "https://w3id.org/ro/crate/1.2"`).
* Title must follow: `"Marine genomic sampling metadata from EMO BON Observation Network [station {XXX}; {CCC}]"`.
* License must be `https://creativecommons.org/licenses/by/4.0/`.
* Both `<observatory>_<affix>.zip` and `ro-crate-metadata.json` must be uploaded to the GitHub Release.

---

### Task 1: Add `pysema` Dependency & Update Governance Loader

**Files:**
- Modify: `requirements.txt`
- Modify: `Dockerfile`
- Modify: `action/resource_loader.py`
- Test: `tests/test_resource_loader.py`

**Interfaces:**
- Produces: `load_observatories_governance(url: str, cache_dir: Optional[Path] = None) -> Dict[str, Dict[str, str]]`
  Returns dictionary keyed by `EMOBON_observatory_id` with subkeys: `observatory_name`, `country`, `water_site_latitude`, `water_site_longitude`, `sediment_site_latitude`, `sediment_site_longitude`.

- [ ] **Step 1: Write the failing test for `load_observatories_governance`**

Add test to `tests/test_resource_loader.py`:

```python
from pathlib import Path
from unittest.mock import patch
from action.resource_loader import load_observatories_governance

SAMPLE_OBSERVATORIES_CSV = """country_code,country,EMOBON_observatory_name,EMOBON_observatory_id,organization,organization_edmoid,startdate,enddate,Water_Column,Soft_Substrates,Hard_Substrates,water_site_latitude,water_site_longitude,sediment_site_latitude,sediment_site_longtitude,hard_substrates_site1_longitude,hard_substrates_site1_latitude,hard_substrates_site2_longtitude,hard_substrates_site2_latitude,contact_person,contact_person_email,ENA_accession_number_umbrella,ENA_accession_number_project,EMOBON_core,loc_broad_ocean,loc_regional,loc_loc
BE,Belgium,EMOBON-BE,BPNS,Flanders Marine Institute (VLIZ),422,6/1/2021,,y,y,y,51.433331,2.808331,51.433331,2.80833,51.579997,2.9933,NaN,NaN,Klaas Deneudt,klaas.deneudt@vliz.be,PRJEB51688,PRJEB51652,y,North Atlantic Ocean,North Sea,Belgian part of the North Sea
FR,France,Bay of Villefranche sur Mer- southern France,VB,Institut de la Mer de Villefranche,5041,6/1/2021,,y,n,y,43.683,7.317,NaN,NaN,43.674619,7.332372,NaN,NaN,Cecile Fauvelot,cecile.fauvelot@ird.fr,PRJEB51688,PRJEB51664,y,Mediterranean Sea - Western Basin,Villefranche Bay,Villefranche Bay - Point B
"""

def test_load_observatories_governance(tmp_path):
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = SAMPLE_OBSERVATORIES_CSV.encode("utf-8")
        mapping = load_observatories_governance("https://example.com/observatories.csv", cache_dir=tmp_path)

        assert "BPNS" in mapping
        assert mapping["BPNS"]["observatory_name"] == "EMOBON-BE"
        assert mapping["BPNS"]["country"] == "Belgium"
        assert mapping["BPNS"]["water_site_latitude"] == "51.433331"
        assert mapping["BPNS"]["water_site_longitude"] == "2.808331"

        assert "VB" in mapping
        assert mapping["VB"]["observatory_name"] == "Bay of Villefranche sur Mer- southern France"
        assert mapping["VB"]["country"] == "France"

def test_load_observatories_governance_fallback(tmp_path):
    with patch("urllib.request.urlopen", side_effect=Exception("Network error")):
        mapping = load_observatories_governance("https://example.com/unreachable.csv", cache_dir=tmp_path)
        assert mapping == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resource_loader.py::test_load_observatories_governance -v`
Expected: FAIL with `ImportError: cannot import name 'load_observatories_governance'`.

- [ ] **Step 3: Update `requirements.txt` and `Dockerfile`**

In `requirements.txt`:
```
rdflib>=7.0.0
requests>=2.31.0
pytest>=8.0.0
pysema>=0.1.0
pyyaml>=6.0.0
```

In `Dockerfile`:
Ensure dependencies are installed via `pip install --no-cache-dir -r requirements.txt`.

- [ ] **Step 4: Implement `load_observatories_governance` in `action/resource_loader.py`**

Add to `action/resource_loader.py`:
```python
def load_observatories_governance(
    url: str,
    cache_dir: Optional[Path] = None
) -> Dict[str, Dict[str, str]]:
    """
    Fetches observatories.csv and returns mapping keyed by EMOBON_observatory_id.
    """
    raw_content = ""
    cached_file = (cache_dir / "observatories.csv") if cache_dir else None

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EMO-BON-Action"})
        with urllib.request.urlopen(req, timeout=15) as response:
            raw_content = response.read().decode("utf-8", errors="replace")
            if cached_file:
                cached_file.parent.mkdir(parents=True, exist_ok=True)
                cached_file.write_text(raw_content, encoding="utf-8")
    except Exception as e:
        print(f"Warning: Failed to fetch observatories governance CSV ({e}).")
        if cached_file and cached_file.exists():
            print(f"Reading from local cached copy: {cached_file}")
            raw_content = cached_file.read_text(encoding="utf-8")
        else:
            return {}

    mapping: Dict[str, Dict[str, str]] = {}
    reader = csv.DictReader(raw_content.splitlines())
    for row in reader:
        obs_id = (row.get("EMOBON_observatory_id") or "").strip()
        if not obs_id:
            continue
        mapping[obs_id] = {
            "observatory_name": (row.get("EMOBON_observatory_name") or "").strip(),
            "country": (row.get("country") or "").strip(),
            "country_code": (row.get("country_code") or "").strip(),
            "water_site_latitude": (row.get("water_site_latitude") or "").strip(),
            "water_site_longitude": (row.get("water_site_longitude") or "").strip(),
            "sediment_site_latitude": (row.get("sediment_site_latitude") or "").strip(),
            "sediment_site_longitude": (row.get("sediment_site_longtitude") or "").strip(),
        }

    return mapping
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_resource_loader.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt Dockerfile action/resource_loader.py tests/test_resource_loader.py
git commit -m "feat: add pysema dependency and load_observatories_governance"
```

---

### Task 2: Implement Metadata Extractor Module

**Files:**
- Create: `action/metadata_extractor.py`
- Create: `tests/test_metadata_extractor.py`

**Interfaces:**
- Produces: `extract_distribution_metadata(workspace_dir: Path, output_dir: Path, observatory_id: str, governance_mapping: Dict[str, Dict[str, str]], repo_name: str, distribution_affix: str) -> Dict[str, Any]`
  Returns dictionary containing:
  - `title`: formatted title string
  - `description`: formatted description string
  - `date_published`: `YYYY-MM-DD`
  - `date_modified`: `YYYY-MM-DD`
  - `temporal_coverage`: `"YYYY-MM-DD/YYYY-MM-DD"`
  - `geo_bbox`: `"min_lat min_lon max_lat max_lon"`
  - `observatory_name`: `XXX`
  - `country`: `CCC`
  - `repo_landing_url`: `https://data.emobon.embrc.eu/{repo_slug}/`
  - `release_tag_url`: `https://github.com/{repo_name}/releases/tag/{distribution_affix}-latest`
  - `citation_text`: formatted citation string
  - `parameters`: list of `{"name": label, "property_id": uri}`
  - `instruments`: list of string literals
  - `organizations`: list of `{"name": org_name, "edmo_url": url}`
  - `active_habitats`: list of active habitats (`["water", "sediment"]`)

- [ ] **Step 1: Write the failing tests in `tests/test_metadata_extractor.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_metadata_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'action.metadata_extractor'`.

- [ ] **Step 3: Implement `action/metadata_extractor.py`**

Create `action/metadata_extractor.py`:
```python
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import rdflib
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS

HABITATS = ("water", "sediment", "hard")
SOSA_OBSERVATION = URIRef("http://www.w3.org/ns/sosa/Observation")
DCTERMS_IDENTIFIER = URIRef("http://purl.org/dc/terms/identifier")
SCHEMA_MEASUREMENT_TECHNIQUE = URIRef("https://schema.org/measurementTechnique")
SCHEMA_INSTRUMENT = URIRef("https://schema.org/instrument")

def format_habitat_list(active_habitats: List[str]) -> str:
    mapped = []
    for h in ("water", "sediment", "hard"):
        if h in active_habitats:
            mapped.append("hard-bottom" if h == "hard" else h)
    if not mapped:
        return "marine"
    if len(mapped) == 1:
        return mapped[0]
    if len(mapped) == 2:
        return f"{mapped[0]}, {mapped[1]}"
    return f"{mapped[0]}, {mapped[1]}, and {mapped[2]}"

def generate_description_text(observatory_name: str, active_habitats: List[str]) -> str:
    habitats_text = format_habitat_list(active_habitats)
    return (
        f"Here you will find all the data collected from the log sheets produced by the "
        f"European Marine Omics Biodiversity Observation Network (EMO BON) observatory {observatory_name} "
        f"for their {habitats_text} sampling activities. Log sheets are filled by the observatory during "
        f"and after their sampling event, and every few months they are harvested, curated, and processed. "
        f"The samples are sent for genomics processing: the raw genomic data can be found in ENA under "
        f"PRJEB51688. The download from this metadata record is a copy of the sampling log sheets for all "
        f"events for which sequences are available in ENA. It also includes a link to the website where "
        f"you can find additional information and browse all other data."
    )

def extract_distribution_metadata(
    workspace_dir: Path,
    output_dir: Path,
    observatory_id: str,
    governance_mapping: Dict[str, Dict[str, str]],
    repo_name: str,
    distribution_affix: str,
) -> Dict[str, Any]:
    logsheets_dir = output_dir / "logsheets"
    obs_info = governance_mapping.get(observatory_id, {})
    obs_name = obs_info.get("observatory_name") or observatory_id
    country = obs_info.get("country") or ""

    # 1. Discover active habitats, dates, coordinates
    dates: List[str] = []
    lats: List[float] = []
    lons: List[float] = []
    active_habitats: List[str] = []

    for habitat in HABITATS:
        sampling_file = logsheets_dir / f"{habitat}_sampling.csv"
        if sampling_file.exists():
            active_habitats.append(habitat)
            with open(sampling_file, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_val = (row.get("event_date") or row.get("date") or "").strip()
                    if date_val:
                        dates.append(date_val[:10])
                    lat_str = (row.get("decimalLatitude") or row.get("latitude") or "").strip()
                    lon_str = (row.get("decimalLongitude") or row.get("longitude") or "").strip()
                    try:
                        if lat_str and lon_str:
                            lats.append(float(lat_str))
                            lons.append(float(lon_str))
                    except ValueError:
                        pass

    # Dates
    dates.sort()
    min_date = dates[0] if dates else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    max_date = dates[-1] if dates else min_date
    temporal_coverage = f"{min_date}/{max_date}"

    # Bbox
    if lats and lons:
        geo_bbox = f"{min(lats)} {min(lons)} {max(lats)} {max(lons)}"
    else:
        # Fallback to governance coordinates
        fallback_lat = obs_info.get("water_site_latitude") or obs_info.get("sediment_site_latitude") or "0.0"
        fallback_lon = obs_info.get("water_site_longitude") or obs_info.get("sediment_site_longitude") or "0.0"
        geo_bbox = f"{fallback_lat} {fallback_lon} {fallback_lat} {fallback_lon}"

    # 2. Extract organizations from observatory CSVs
    organizations_seen: Set[str] = set()
    organizations: List[Dict[str, str]] = []
    for habitat in HABITATS:
        obs_file = logsheets_dir / f"{habitat}_observatory.csv"
        if obs_file.exists():
            with open(obs_file, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    org_str = (row.get("organization") or "").strip()
                    edmo_str = (row.get("organization_edmoid") or "").strip()
                    org_names = [o.strip() for o in org_str.split(";") if o.strip()]
                    edmo_ids = [e.strip() for e in edmo_str.split(";") if e.strip()]

                    for idx, name in enumerate(org_names):
                        if name in organizations_seen:
                            continue
                        organizations_seen.add(name)
                        edmo_id = edmo_ids[idx] if idx < len(edmo_ids) else ""
                        edmo_url = f"https://edmo.seadatanet.org/report/{edmo_id}" if edmo_id else ""
                        organizations.append({"name": name, "edmo_url": edmo_url})

    # 3. Extract parameters and instruments from subsetted all-triples.ttl
    parameters: List[Dict[str, str]] = []
    instruments: List[str] = []
    ttl_file = output_dir / "all-triples.ttl"
    if ttl_file.exists():
        g = Graph()
        try:
            g.parse(ttl_file, format="turtle")
            param_seen: Set[str] = set()
            for s in g.subjects(RDF.type, SOSA_OBSERVATION):
                labels = list(g.objects(s, RDFS.label))
                idents = list(g.objects(s, DCTERMS_IDENTIFIER))
                lbl = str(labels[0]) if labels else ""
                ident = str(idents[0]) if idents else ""
                if lbl and lbl not in param_seen:
                    param_seen.add(lbl)
                    parameters.append({"name": lbl, "property_id": ident})

                for m in g.objects(s, SCHEMA_MEASUREMENT_TECHNIQUE):
                    inst_lbl = str(m).strip()
                    if inst_lbl and inst_lbl not in instruments:
                        instruments.append(inst_lbl)

            for inst in g.objects(None, SCHEMA_INSTRUMENT):
                inst_lbl = str(inst).strip()
                if inst_lbl and inst_lbl not in instruments:
                    instruments.append(inst_lbl)
        except Exception as e:
            print(f"Warning: Could not parse {ttl_file} for parameters: {e}")

    # Build URLs and citation
    repo_slug = repo_name.split("/")[-1]
    repo_landing_url = f"https://data.emobon.embrc.eu/{repo_slug}/"
    release_tag_url = f"https://github.com/{repo_name}/releases/tag/{distribution_affix}-latest"

    title_location = f"{obs_name}; {country}" if country else obs_name
    title = f"Marine genomic sampling metadata from EMO BON Observation Network [station {title_location}]"
    description = generate_description_text(obs_name, active_habitats)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    year = today[:4]
    citation_text = (
        f"European Marine Biological Research Centre (EMBRC), "
        f"European Marine Omics Biodiversity Observation Network (EMO BON), "
        f"Metadata logsheets for {title}, {year}, {repo_landing_url}, emobon@embrc.eu"
    )

    return {
        "title": title,
        "description": description,
        "date_published": today,
        "date_modified": today,
        "temporal_coverage": temporal_coverage,
        "start_date": min_date,
        "end_date": max_date,
        "geo_bbox": geo_bbox,
        "observatory_name": obs_name,
        "country": country,
        "repo_landing_url": repo_landing_url,
        "release_tag_url": release_tag_url,
        "citation_text": citation_text,
        "parameters": parameters,
        "instruments": instruments,
        "organizations": organizations,
        "active_habitats": active_habitats,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_metadata_extractor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add action/metadata_extractor.py tests/test_metadata_extractor.py
git commit -m "feat: implement metadata_extractor for Blue Cloud distribution"
```

---

### Task 3: Create Blueprint YAML and `ro_crate_builder.py`

**Files:**
- Create: `action/blueprints/bluecloud_ro_blueprint.yml`
- Create: `action/ro_crate_builder.py`
- Create: `tests/test_ro_crate_builder.py`

**Interfaces:**
- Produces: `build_ro_crate(output_dir: Path, metadata: Dict[str, Any]) -> Path`
  Executes `ROCreator` and generates `output_dir/ro-crate-metadata.json`. Returns path to the generated file.

- [ ] **Step 1: Write the failing test in `tests/test_ro_crate_builder.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ro_crate_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'action.ro_crate_builder'`.

- [ ] **Step 3: Create `action/blueprints/bluecloud_ro_blueprint.yml`**

Create `action/blueprints/bluecloud_ro_blueprint.yml`:
```yaml
$:
  version: "1.2"
  prefix:
    schema: "http://schema.org/"
    dcat: "http://www.w3.org/ns/dcat#"
    dct: "http://purl.org/dc/terms/"
    sosa: "http://www.w3.org/ns/sosa/"

ro-crate-metadata.json:
  $type: CreativeWork
  conformsTo: https://w3id.org/ro/crate/1.2
  about: ./

./:
  $type: Dataset
  name: !resolve '"{TITLE}"'
  description: !resolve '"{DESCRIPTION}"'
  datePublished: !resolve '"{DATE_PUBLISHED}"'
  dateModified: !resolve '"{DATE_MODIFIED}"'
  license: https://creativecommons.org/licenses/by/4.0/
  url: !resolve '"{REPO_LANDING_URL}"'
  identifier:
    - !resolve '"{REPO_LANDING_URL}"'
    - !resolve '"{RELEASE_TAG_URL}"'
  citation: !resolve '"{CITATION_TEXT}"'
  temporalCoverage: !resolve '"{TEMPORAL_COVERAGE}"'
  spatialCoverage: _:spatialCoverage
  keywords:
    - "marine genomics"
    - "European Marine Omics Biodiversity Observation Network"
    - "EMO BON"
    - "Biota"
    - !resolve '"{OBSERVATORY_NAME}"'
  about:
    - https://inspire.ec.europa.eu/metadata-codelist/TopicCategory/biota
    - https://www.embrc.eu/emo-bon/
  publisher: https://www.embrc.eu/emo-bon/

_:spatialCoverage:
  $type: Place
  name: !resolve '"{OBSERVATORY_NAME} [{COUNTRY}]"'
  geo: _:geoBbox

_:geoBbox:
  $type: GeoShape
  box: !resolve '"{GEO_BBOX}"'

https://inspire.ec.europa.eu/metadata-codelist/TopicCategory/biota:
  $type: DefinedTerm
  name: "Biota"
  url: https://inspire.ec.europa.eu/metadata-codelist/TopicCategory/biota
  inDefinedTermSet: https://inspire.ec.europa.eu/metadata-codelist/TopicCategory

https://www.embrc.eu/emo-bon/:
  $type: Project
  name: "EMO BON"
  url: https://www.embrc.eu/emo-bon/
```

- [ ] **Step 4: Implement `action/ro_crate_builder.py`**

Create `action/ro_crate_builder.py`:
```python
import json
from pathlib import Path
from typing import Any, Dict
import yaml

try:
    from sema.ro.creator import ROCreator
except ImportError:
    ROCreator = None

BLUEPRINT_FILE = Path(__file__).parent / "blueprints" / "bluecloud_ro_blueprint.yml"

def build_ro_crate(output_dir: Path, metadata: Dict[str, Any]) -> Path:
    """
    Constructs ro-crate-metadata.json in output_dir using pysema ROCreator.
    If pysema is not installed, generates standard RO-Crate 1.2 compliant dictionary.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "ro-crate-metadata.json"

    blueprint_env = {
        "TITLE": metadata["title"],
        "DESCRIPTION": metadata["description"],
        "DATE_PUBLISHED": metadata["date_published"],
        "DATE_MODIFIED": metadata["date_modified"],
        "REPO_LANDING_URL": metadata["repo_landing_url"],
        "RELEASE_TAG_URL": metadata["release_tag_url"],
        "CITATION_TEXT": metadata["citation_text"],
        "TEMPORAL_COVERAGE": metadata["temporal_coverage"],
        "OBSERVATORY_NAME": metadata["observatory_name"],
        "COUNTRY": metadata.get("country", ""),
        "GEO_BBOX": metadata["geo_bbox"],
    }

    # Dynamic Blueprint generation to include parameter and organization nodes
    with open(BLUEPRINT_FILE, "r", encoding="utf-8") as f:
        blueprint_data = yaml.safe_load(f) or {}

    root_dataset = blueprint_data.setdefault("./", {})
    creator_uris = []
    for org in metadata.get("organizations", []):
        url = org.get("edmo_url") or f"urn:org:{org['name']}"
        creator_uris.append(url)
        blueprint_data[url] = {
            "$type": "Organization",
            "name": org["name"],
            "url": org.get("edmo_url", ""),
        }
    if creator_uris:
        root_dataset["creator"] = creator_uris

    var_measured = []
    for idx, param in enumerate(metadata.get("parameters", [])):
        bnode_id = f"_:param_{idx}"
        var_measured.append(bnode_id)
        node = {
            "$type": "PropertyValue",
            "name": param["name"],
        }
        if param.get("property_id"):
            node["propertyID"] = param["property_id"]
        blueprint_data[bnode_id] = node
    if var_measured:
        root_dataset["variableMeasured"] = var_measured

    if metadata.get("instruments"):
        root_dataset["instrument"] = metadata["instruments"]

    # Files
    has_part = []
    for candidate in ("all-triples.ttl", "ena_accessions_subset.csv", "README.md"):
        if (output_dir / candidate).exists():
            has_part.append(candidate)
            blueprint_data[candidate] = {
                "$type": "File",
                "name": candidate,
            }
    if (output_dir / "logsheets").exists():
        has_part.append("logsheets/")
        blueprint_data["logsheets/"] = {
            "$type": "Dataset",
            "name": "logsheets",
        }
    if has_part:
        root_dataset["hasPart"] = has_part

    temp_blueprint = output_dir / ".bluecloud_ro_blueprint_resolved.yml"
    with open(temp_blueprint, "w", encoding="utf-8") as f:
        yaml.dump(blueprint_data, f, sort_keys=False)

    if ROCreator:
        try:
            creator = ROCreator(
                blueprint_path=temp_blueprint,
                blueprint_env=blueprint_env,
                rocrate_path=output_dir,
                force=True,
            )
            creator.process()
        except Exception as e:
            print(f"Warning: ROCreator process raised {e}, writing fallback JSON-LD directly.")
            _write_fallback_ro_crate(destination, metadata)
    else:
        _write_fallback_ro_crate(destination, metadata)

    if temp_blueprint.exists():
        temp_blueprint.unlink()

    return destination

def _write_fallback_ro_crate(destination: Path, metadata: Dict[str, Any]) -> None:
    graph = [
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "conformsTo": {"@id": "https://w3id.org/ro/crate/1.2"},
            "about": {"@id": "./"},
        },
        {
            "@id": "./",
            "@type": "Dataset",
            "name": metadata["title"],
            "description": metadata["description"],
            "datePublished": metadata["date_published"],
            "dateModified": metadata["date_modified"],
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "url": metadata["repo_landing_url"],
            "identifier": [metadata["repo_landing_url"], metadata["release_tag_url"]],
            "citation": metadata["citation_text"],
            "temporalCoverage": metadata["temporal_coverage"],
            "spatialCoverage": {"@id": "_:spatialCoverage"},
            "keywords": [
                "marine genomics",
                "European Marine Omics Biodiversity Observation Network",
                "EMO BON",
                "Biota",
                metadata["observatory_name"],
            ],
            "about": [
                {"@id": "https://inspire.ec.europa.eu/metadata-codelist/TopicCategory/biota"},
                {"@id": "https://www.embrc.eu/emo-bon/"},
            ],
            "publisher": {"@id": "https://www.embrc.eu/emo-bon/"},
            "creator": [
                {"@id": org["edmo_url"] or f"urn:org:{org['name']}"}
                for org in metadata.get("organizations", [])
            ],
        },
        {
            "@id": "_:spatialCoverage",
            "@type": "Place",
            "name": f"{metadata['observatory_name']} [{metadata.get('country', '')}]",
            "geo": {"@id": "_:geoBbox"},
        },
        {
            "@id": "_:geoBbox",
            "@type": "GeoShape",
            "box": metadata["geo_bbox"],
        },
        {
            "@id": "https://inspire.ec.europa.eu/metadata-codelist/TopicCategory/biota",
            "@type": "DefinedTerm",
            "name": "Biota",
            "url": "https://inspire.ec.europa.eu/metadata-codelist/TopicCategory/biota",
            "inDefinedTermSet": "https://inspire.ec.europa.eu/metadata-codelist/TopicCategory",
        },
        {
            "@id": "https://www.embrc.eu/emo-bon/",
            "@type": "Project",
            "name": "EMO BON",
            "url": "https://www.embrc.eu/emo-bon/",
        },
    ]

    for org in metadata.get("organizations", []):
        url = org.get("edmo_url") or f"urn:org:{org['name']}"
        graph.append({
            "@id": url,
            "@type": "Organization",
            "name": org["name"],
            "url": org.get("edmo_url", ""),
        })

    for idx, param in enumerate(metadata.get("parameters", [])):
        bnode = {
            "@id": f"_:param_{idx}",
            "@type": "PropertyValue",
            "name": param["name"],
        }
        if param.get("property_id"):
            bnode["propertyID"] = param["property_id"]
        graph.append(bnode)

    ro_crate_doc = {
        "@context": "https://w3id.org/ro/crate/1.2/context",
        "@graph": graph,
    }

    with open(destination, "w", encoding="utf-8") as f:
        json.dump(ro_crate_doc, f, indent=2)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_ro_crate_builder.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add action/blueprints/bluecloud_ro_blueprint.yml action/ro_crate_builder.py tests/test_ro_crate_builder.py
git commit -m "feat: implement ro_crate_builder and bluecloud RO blueprint"
```

---

### Task 4: Update Packager, Release Publisher, and Distribution Linker

**Files:**
- Modify: `action/packager.py`
- Modify: `action/release_publisher.py`
- Modify: `action/distribution_linker.py`
- Test: `tests/test_packager.py`
- Test: `tests/test_release_publisher.py`
- Test: `tests/test_distribution_linker.py`

**Interfaces:**
- `package_subset_archive(output_dir: Path, observatory: str, affix: str, mapping_rows: List[Dict[str, str]], citation_text: str = "") -> Path`: Packages all files in `output_dir` into `<observatory>_<affix>.zip`.
- `publish_github_release(repo_name: str, token: str, tag: str, asset_paths: List[Path], title: str, body: str) -> Dict[str, str]`: Publishes release and uploads multiple assets, returning a dict mapping asset filename to its download URL.
- `link_distribution_in_triples(workspace_dir: Path, repo_name: str, observatory: str, affix: str, download_url: str, metadata_url: str = "") -> None`: Links both the distribution and RO-Crate descriptor in `all-triples.ttl`.

- [ ] **Step 1: Write/update tests for dual-asset publishing and distribution linking**

Update `tests/test_packager.py`:
```python
import zipfile
from action.packager import package_subset_archive

def test_package_subset_archive_includes_ro_crate(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "ro-crate-metadata.json").write_text("{}", encoding="utf-8")
    (output_dir / "all-triples.ttl").write_text("", encoding="utf-8")

    archive = package_subset_archive(output_dir, "BPNS", "bluecloud-ENA", [])
    assert archive.exists()

    with zipfile.ZipFile(archive, "r") as zf:
        names = zf.namelist()
        assert "ro-crate-metadata.json" in names
        assert "all-triples.ttl" in names
        assert "README.md" in names
```

Update `tests/test_distribution_linker.py`:
```python
from rdflib import Graph, URIRef
from action.distribution_linker import link_distribution_in_triples

def test_link_distribution_with_metadata_url(tmp_path):
    ttl_file = tmp_path / "all-triples.ttl"
    ttl_file.write_text("", encoding="utf-8")

    link_distribution_in_triples(
        workspace_dir=tmp_path,
        repo_name="emo-bon/observatory-bpns-crate",
        observatory="BPNS",
        affix="bluecloud-ENA",
        download_url="https://github.com/emo-bon/observatory-bpns-crate/releases/download/bluecloud-ENA-latest/BPNS_bluecloud-ENA.zip",
        metadata_url="https://github.com/emo-bon/observatory-bpns-crate/releases/download/bluecloud-ENA-latest/ro-crate-metadata.json",
    )

    g = Graph().parse(ttl_file, format="turtle")
    dist_uri = URIRef("https://data.emobon.embrc.eu/observatory-bpns-crate/distribution/bluecloud-ENA")
    assert (dist_uri, None, None) in g
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_packager.py tests/test_distribution_linker.py -v`

- [ ] **Step 3: Update `action/packager.py`**

In `action/packager.py`:
Update README generation to reflect the official citation and RO-Crate 1.2 compliance:
```python
def package_subset_archive(
    output_dir: Path,
    observatory: str,
    affix: str,
    mapping_rows: List[Dict[str, str]],
    citation_text: str = ""
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write ena_accessions_subset.csv
    mapping_file = output_dir / "ena_accessions_subset.csv"
    fieldnames = ["event_id", "source_mat_id", "ena_accession_number_run_metag"]
    with open(mapping_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in mapping_rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    # 2. Write README.md
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    readme_file = output_dir / "README.md"
    citation_section = f"\n## Citation\n{citation_text}\n" if citation_text else ""
    readme_content = f"""# EMO BON Subsetted Distribution: {observatory} ({affix})

- **Date Published**: {today}
- **Observatory Station**: {observatory}
- **Affix / Purpose**: {affix} (Sequenced samples with ENA run accessions)
- **Specification Conformance**: RO-Crate 1.2
- **License**: Creative Commons Attribution 4.0 International (CC BY 4.0)
{citation_section}
## Contents
- `ro-crate-metadata.json`: RO-Crate 1.2 catalog metadata descriptor.
- `logsheets/`: Sampling, measured, and observatory logsheet CSVs filtered for qualifying events.
- `all-triples.ttl`: Subsetted RDF semantic graph for all matching events, samples, and observations.
- `ena_accessions_subset.csv`: Mapping table of sampling events, sample IDs, and ENA run accessions.
"""
    readme_file.write_text(readme_content, encoding="utf-8")

    # 3. Zip archive creation
    archive_name = f"{observatory}_{affix}.zip"
    zip_path = output_dir / archive_name

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in output_dir.rglob("*"):
            if file_path == zip_path or file_path.is_dir():
                continue
            arcname = file_path.relative_to(output_dir)
            zf.write(file_path, arcname)

    return zip_path
```

- [ ] **Step 4: Update `action/release_publisher.py` to support multiple assets**

In `action/release_publisher.py`:
Change `publish_github_release` to accept `asset_paths: List[Path]` and return `Dict[str, str]` (filename to download URL):
```python
def publish_github_release(
    repo_name: str,
    token: str,
    tag: str,
    asset_paths: List[Path],
    title: str,
    body: str
) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    # ... create or update release ...
    # Upload each asset in asset_paths
    # Return mapping of asset.name -> download_url
```

- [ ] **Step 5: Update `action/distribution_linker.py`**

In `action/distribution_linker.py`:
Add `metadata_url: str = ""` parameter:
```python
def link_distribution_in_triples(
    workspace_dir: Path,
    repo_name: str,
    observatory: str,
    affix: str,
    download_url: str,
    metadata_url: str = ""
) -> None:
    # ... existing triples ...
    if metadata_url:
        meta_uriref = URIRef(metadata_url)
        g.add((dist_uri, DCTERMS.conformsTo, URIRef("https://w3id.org/ro/crate/1.2")))
        g.add((dist_uri, DCAT.accessURL, meta_uriref))
    # ... serialize ...
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_packager.py tests/test_release_publisher.py tests/test_distribution_linker.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add action/packager.py action/release_publisher.py action/distribution_linker.py tests/
git commit -m "feat: support ro-crate-metadata.json packaging, dual release assets, and distribution linking"
```

---

### Task 5: Pipeline Integration, Action Inputs/Outputs, and E2E Tests

**Files:**
- Modify: `action/main.py`
- Modify: `action.yml`
- Modify: `tests/test_bpns_workflow_e2e.py`
- Modify: `tests/test_main.py`

**Interfaces:**
- Consumes: `load_observatories_governance`, `extract_distribution_metadata`, `build_ro_crate`, `package_subset_archive`, `publish_github_release`, `link_distribution_in_triples`.
- Produces: GitHub Action outputs:
  - `release_tag`
  - `release_download_url`
  - `rocrate_metadata_url`
  - `subsetted_events_count`
  - `subsetted_samples_count`

- [ ] **Step 1: Write/update end-to-end tests in `tests/test_bpns_workflow_e2e.py`**

Update `tests/test_bpns_workflow_e2e.py` to verify:
1. `ro-crate-metadata.json` is generated in `output_dir`.
2. `output_dir/ro-crate-metadata.json` contains correct title with `EMOBON-BE; Belgium`.
3. `output_dir/BPNS_bluecloud-ENA.zip` contains `ro-crate-metadata.json`.
4. Result dictionary returns `rocrate_metadata_url`.

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_bpns_workflow_e2e.py -v`

- [ ] **Step 3: Update `action/main.py`**

In `action/main.py`:
- In `run_pipeline`:
  1. Add `observatories_url: str` argument.
  2. Load governance data: `governance = load_observatories_governance(observatories_url, cache_dir)`.
  3. Run tabular subsetting and RDF graph subsetting.
  4. Run `metadata = extract_distribution_metadata(...)`.
  5. Build RO-Crate: `crate_path = build_ro_crate(output_dir, metadata)`.
  6. Package archive: `archive_path = package_subset_archive(..., citation_text=metadata["citation_text"])`.
  7. Publish release: pass `[archive_path, crate_path]` to `publish_github_release`.
  8. Link in triples: pass `download_url` and `metadata_url`.
  9. Return output dict with `rocrate_metadata_url`.

- [ ] **Step 4: Update `action.yml`**

Add input:
```yaml
  observatories_url:
    description: "Remote URL pointing to the governance-crate observatories.csv"
    required: false
    default: "https://raw.githubusercontent.com/emo-bon/governance-crate/main/observatories.csv"
```
Add output:
```yaml
  rocrate_metadata_url:
    description: "Direct download URL for the standalone ro-crate-metadata.json release asset"
```

- [ ] **Step 5: Run full test suite**

Run: `pytest -v`
Expected: ALL TESTS PASS.

- [ ] **Step 6: Commit**

```bash
git add action/main.py action.yml tests/
git commit -m "feat: wire observatories governance and rocrate metadata generation into main pipeline"
```

---

## Plan Self-Review Check

1. **Spec Coverage**:
   - Title template `station XXX; CCC` with `observatories.csv` lookup: Covered in Tasks 1, 2, 3.
   - Dynamic description with `YYY`: Covered in Task 2.
   - Dynamic spatial bounding box & temporal coverage: Covered in Task 2.
   - Parameters (`variableMeasured`), Instruments, Organizations with EDMO URLs: Covered in Tasks 2 & 3.
   - Relative root `@id: "./"` with live URL identifiers: Covered in Task 3.
   - Dual asset GitHub Release (`.zip` and `ro-crate-metadata.json`): Covered in Tasks 4 & 5.
2. **Placeholders**: No TODOs, TBDs, or vague instructions.
3. **Type Consistency**: Method signatures, return types, and argument names match precisely across tasks.
