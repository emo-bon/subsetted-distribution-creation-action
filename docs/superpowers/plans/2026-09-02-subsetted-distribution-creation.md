# Subsetted Distribution Creation Action Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Docker-based GitHub Action that subsets EMO BON observatory data (CSVs and RDF triples) based on ENA run accession numbers, packages them into a release archive, publishes a GitHub release at `<affix>-latest`, and links the distribution into the observatory's `all-triples.ttl`.

**Architecture:** A Python-based containerized action split into modular components: remote resource loader (ENA CSV ingestion), tabular subsetter (logsheet CSV filtering), graph subsetter (`rdflib` subgraph traversal), archive packager, GitHub Release publisher (REST API), and semantic distribution linker.

**Tech Stack:** Python 3.11+, `rdflib`, `requests`, `pyyaml`, `pytest`, Docker, GitHub Actions API.

**Spec:** [docs/superpowers/specs/2026-09-02-subsetted-distribution-creation-design.md](file:///c:/Users/cedricd/Documents/Github/subsetted-distribution-creation-action/docs/superpowers/specs/2026-09-02-subsetted-distribution-creation-design.md)

## Global Constraints
- Python: standard library + `rdflib>=7.0.0`, `requests>=2.31.0`, `pyyaml>=6.0.1`, `pytest>=8.0.0`.
- Docker base image: `python:3.11-slim`.
- Stable floating release tag: `<distribution_affix>-latest` (default: `bluecloud-ENA-latest`).
- Archive filename convention: `<observatory>_<distribution_affix>.zip`.
- Workspace isolation: Extra remote resources are written to `.subsetted_cache/`; staged release files to `output_dir` (default: `subsetted_distribution`).
- Existing `all-triples.ttl` prefixes and triples must be preserved during distribution metadata injection.

---

### Task 1: Scaffolding, Dependencies, and Test Harness

**Files:**
- Create: `requirements.txt`
- Create: `action.yml`
- Create: `Dockerfile`
- Create: `entrypoint.sh`
- Create: `action/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Produces: Base project structure and operational test runner.

- [ ] **Step 1: Write requirements.txt**

```txt
rdflib>=7.0.0
requests>=2.31.0
pyyaml>=6.0.1
pytest>=8.0.0
```

- [ ] **Step 2: Write action.yml**

```yaml
name: 'subsetted-distribution-creation-action'
description: 'Subsets observatory data linked to ENA run accessions and creates distribution release assets'
author: 'EMO BON'
inputs:
  ena_records_url:
    description: 'Remote URL pointing to the ENA run accessions CSV'
    required: false
    default: 'https://raw.githubusercontent.com/emo-bon/sequencing-logistics-crate/main/ena-accession-numbers-batches1-2.csv'
  remote_resources:
    description: 'Optional YAML/JSON string specifying additional remote key-value URLs to fetch'
    required: false
    default: ''
  distribution_affix:
    description: 'Affix appended to observatory name for release tag and asset filename'
    required: false
    default: 'bluecloud-ENA'
  output_dir:
    description: 'Local workspace staging directory for subsetted artifacts'
    required: false
    default: 'subsetted_distribution'
  create_release:
    description: 'Whether to publish or update the GitHub Release'
    required: false
    default: 'true'
  github_token:
    description: 'GitHub token for release creation'
    required: false
    default: ${{ github.token }}
outputs:
  release_tag:
    description: 'Release tag created or updated'
  release_download_url:
    description: 'Direct download URL for the archive asset'
  subsetted_events_count:
    description: 'Number of qualifying events in the subset'
  subsetted_samples_count:
    description: 'Number of sample IDs in the subset'
runs:
  using: 'docker'
  image: 'Dockerfile'
```

- [ ] **Step 3: Write Dockerfile and entrypoint.sh**

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY action /app/action
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
```

```bash
#!/bin/sh
set -e
python -m action.main
```

- [ ] **Step 4: Create package markers and tests/conftest.py**

Create empty `action/__init__.py` and `tests/__init__.py`.
Create `tests/conftest.py`:
```python
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 5: Verify test harness runs**

Run: `pytest -v`
Expected: `no tests ran in ...` with exit code 5 (or 0 with no errors).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt action.yml Dockerfile entrypoint.sh action/__init__.py tests/__init__.py tests/conftest.py
git commit -m "chore: scaffold project structure, dockerfile, and test harness"
```

---

### Task 2: Remote Resource Loader (`action/resource_loader.py`)

**Files:**
- Create: `action/resource_loader.py`
- Test: `tests/test_resource_loader.py`

**Interfaces:**
- Produces:
  `load_ena_qualifying_events(ena_url: str) -> tuple[set[str], list[dict[str, str]]]`
  `fetch_remote_resources(remote_resources_raw: str, cache_dir: Path) -> dict[str, Path]`

- [ ] **Step 1: Write the failing test for ENA loading and remote resources**

Create `tests/test_resource_loader.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resource_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'action.resource_loader'`.

- [ ] **Step 3: Write implementation in action/resource_loader.py**

Create `action/resource_loader.py`:
```python
import csv
import io
import json
import urllib.request
from pathlib import Path
from typing import Dict, List, Set, Tuple
import yaml

def load_ena_qualifying_events(ena_url: str) -> Tuple[Set[str], List[Dict[str, str]]]:
    """
    Fetches the ENA CSV and extracts events that have a non-empty ena_accession_number_run_metag.
    Returns (set_of_qualifying_event_ids, list_of_mapping_records).
    """
    req = urllib.request.Request(ena_url, headers={"User-Agent": "subsetted-distribution-creation-action"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read().decode("utf-8")

    reader = csv.DictReader(io.StringIO(content))
    qualifying_events: Set[str] = set()
    mapping_rows: List[Dict[str, str]] = []

    for row in reader:
        run_acc = (row.get("ena_accession_number_run_metag") or "").strip()
        event_id = (row.get("event_id") or "").strip()
        source_mat_id = (row.get("source_mat_id") or "").strip()

        if run_acc and event_id:
            qualifying_events.add(event_id)
            mapping_rows.append({
                "event_id": event_id,
                "source_mat_id": source_mat_id,
                "ena_accession_number_run_metag": run_acc
            })

    return qualifying_events, mapping_rows

def fetch_remote_resources(remote_resources_raw: str, cache_dir: Path) -> Dict[str, Path]:
    """
    Parses YAML/JSON specifying additional remote URLs and downloads them into cache_dir.
    """
    if not remote_resources_raw or not remote_resources_raw.strip():
        return {}

    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        data = yaml.safe_load(remote_resources_raw)
    except Exception:
        data = json.loads(remote_resources_raw)

    if not isinstance(data, dict):
        return {}

    downloaded: Dict[str, Path] = {}
    for name, url in data.items():
        if not isinstance(url, str) or not url.startswith("http"):
            continue
        dest_file = cache_dir / f"{name}.csv"
        req = urllib.request.Request(url, headers={"User-Agent": "subsetted-distribution-creation-action"})
        with urllib.request.urlopen(req, timeout=30) as resp, open(dest_file, "wb") as out_f:
            out_f.write(resp.read())
        downloaded[name] = dest_file

    return downloaded
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_resource_loader.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add action/resource_loader.py tests/test_resource_loader.py
git commit -m "feat: implement ENA and remote resource loader"
```

---

### Task 3: Tabular Subsetter (`action/tabular_subsetter.py`)

**Files:**
- Create: `action/tabular_subsetter.py`
- Test: `tests/test_tabular_subsetter.py`

**Interfaces:**
- Consumes: `qualifying_event_ids: set[str]` from `resource_loader`
- Produces: `subset_logsheets(workspace_dir: Path, output_dir: Path, qualifying_events: set[str]) -> tuple[int, int, set[str]]`
  Returns `(retained_events_count, retained_samples_count, retained_sample_ids)`.

- [ ] **Step 1: Write the failing test for tabular subsetting**

Create `tests/test_tabular_subsetter.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tabular_subsetter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'action.tabular_subsetter'`.

- [ ] **Step 3: Write implementation in action/tabular_subsetter.py**

Create `action/tabular_subsetter.py`:
```python
import csv
import shutil
from pathlib import Path
from typing import Set, Tuple

HABITATS = ("water", "sediment", "hard")

def subset_logsheets(
    workspace_dir: Path,
    output_dir: Path,
    qualifying_events: Set[str]
) -> Tuple[int, int, Set[str]]:
    """
    Subsets CSV logsheets in logsheets/transformed (or logsheets/raw) to output_dir/logsheets.
    Returns (retained_events_count, retained_samples_count, retained_sample_ids).
    """
    logsheets_src = workspace_dir / "logsheets" / "transformed"
    if not logsheets_src.exists():
        logsheets_src = workspace_dir / "logsheets" / "raw"

    out_logsheets = output_dir / "logsheets"
    out_logsheets.mkdir(parents=True, exist_ok=True)

    if not logsheets_src.exists():
        return 0, 0, set()

    retained_sample_ids: Set[str] = set()
    retained_events: Set[str] = set()

    for habitat in HABITATS:
        sampling_file = logsheets_src / f"{habitat}_sampling.csv"
        measured_file = logsheets_src / f"{habitat}_measured.csv"
        observatory_file = logsheets_src / f"{habitat}_observatory.csv"

        habitat_sample_ids: Set[str] = set()

        # 1. Process sampling file
        if sampling_file.exists():
            with open(sampling_file, "r", encoding="utf-8", errors="replace") as in_f:
                reader = csv.DictReader(in_f)
                fieldnames = reader.fieldnames or []
                matching_rows = []
                for row in reader:
                    ev = (row.get("sampling_event") or "").strip()
                    if ev in qualifying_events:
                        matching_rows.append(row)
                        retained_events.add(ev)
                        sm_id = (row.get("source_mat_id") or "").strip()
                        sm_orig = (row.get("source_mat_id_orig") or "").strip()
                        if sm_id:
                            retained_sample_ids.add(sm_id)
                            habitat_sample_ids.add(sm_id)
                        if sm_orig:
                            retained_sample_ids.add(sm_orig)
                            habitat_sample_ids.add(sm_orig)

            if matching_rows:
                out_sampling = out_logsheets / f"{habitat}_sampling.csv"
                with open(out_sampling, "w", newline="", encoding="utf-8") as out_f:
                    writer = csv.DictWriter(out_f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(matching_rows)

        # 2. Process measured file
        if measured_file.exists():
            with open(measured_file, "r", encoding="utf-8", errors="replace") as in_f:
                reader = csv.DictReader(in_f)
                fieldnames = reader.fieldnames or []
                matching_rows = []
                for row in reader:
                    sm_id = (row.get("source_mat_id") or "").strip()
                    sm_orig = (row.get("source_mat_id_orig") or "").strip()
                    if sm_id in habitat_sample_ids or sm_orig in habitat_sample_ids:
                        matching_rows.append(row)

            if matching_rows:
                out_measured = out_logsheets / f"{habitat}_measured.csv"
                with open(out_measured, "w", newline="", encoding="utf-8") as out_f:
                    writer = csv.DictWriter(out_f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(matching_rows)

        # 3. Copy observatory file in full
        if observatory_file.exists():
            shutil.copy2(observatory_file, out_logsheets / f"{habitat}_observatory.csv")

    # Count distinct source_mat_id / source_mat_id_orig
    return len(retained_events), len(retained_sample_ids), retained_sample_ids
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tabular_subsetter.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add action/tabular_subsetter.py tests/test_tabular_subsetter.py
git commit -m "feat: implement tabular logsheet subsetter"
```

---

### Task 4: RDF Graph Subsetter (`action/graph_subsetter.py`)

**Files:**
- Create: `action/graph_subsetter.py`
- Test: `tests/test_graph_subsetter.py`

**Interfaces:**
- Consumes: `all-triples.ttl` from repository root and `qualifying_events: set[str]`.
- Produces: `subset_rdf_graph(workspace_dir: Path, output_dir: Path, qualifying_events: set[str]) -> Path`
  Serializes extracted subgraph to `<output_dir>/all-triples.ttl`.

- [ ] **Step 1: Write the failing test for RDF graph subsetting**

Create `tests/test_graph_subsetter.py`:
```python
from pathlib import Path
import rdflib
from action.graph_subsetter import subset_rdf_graph

SAMPLE_TURTLE = """
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix emobon-core: <https://data.emobon.embrc.eu/ns/core#> .
@prefix qudt: <http://qudt.org/schema/qudt/> .

<http://example.org/event/BPNS_So_210726> a sosa:Sampling, prov:Activity ;
    sosa:resultTime "2021-07-26" .

<http://example.org/sample/EMOBON_BPNS_So_5> a sosa:Sample ;
    sosa:isResultOf <http://example.org/event/BPNS_So_210726> .

<http://example.org/obs/1> a sosa:Observation ;
    sosa:hasFeatureOfInterest <http://example.org/sample/EMOBON_BPNS_So_5> ;
    sosa:hasResult [ a qudt:QuantityValue ; qudt:numericValue 7.5 ] .

# Unrelated event
<http://example.org/event/BPNS_So_999999> a sosa:Sampling ;
    sosa:resultTime "2099-01-01" .
<http://example.org/sample/EMOBON_BPNS_So_99> a sosa:Sample ;
    sosa:isResultOf <http://example.org/event/BPNS_So_999999> .

<http://example.org/observatory/BPNS> a emobon-core:Observatory ;
    emobon-core:observatoryId "BPNS" .
"""

def test_subset_rdf_graph(tmp_path: Path):
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "output"
    workspace.mkdir()
    ttl_file = workspace / "all-triples.ttl"
    ttl_file.write_text(SAMPLE_TURTLE)

    out_ttl = subset_rdf_graph(workspace, out_dir, {"BPNS_So_210726"})

    assert out_ttl.exists()
    g = rdflib.Graph()
    g.parse(out_ttl, format="turtle")

    # Target event and its samples/observations should exist
    assert (rdflib.URIRef("http://example.org/event/BPNS_So_210726"), None, None) in g
    assert (rdflib.URIRef("http://example.org/sample/EMOBON_BPNS_So_5"), None, None) in g
    assert (rdflib.URIRef("http://example.org/obs/1"), None, None) in g

    # Observatory entity should exist
    assert (rdflib.URIRef("http://example.org/observatory/BPNS"), None, None) in g

    # Unrelated event and sample must NOT exist
    assert (rdflib.URIRef("http://example.org/event/BPNS_So_999999"), None, None) not in g
    assert (rdflib.URIRef("http://example.org/sample/EMOBON_BPNS_So_99"), None, None) not in g
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_subsetter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'action.graph_subsetter'`.

- [ ] **Step 3: Write implementation in action/graph_subsetter.py**

Create `action/graph_subsetter.py`:
```python
from pathlib import Path
from typing import Set
import rdflib
from rdflib import BNode, Graph, URIRef
from rdflib.namespace import RDF

SOSA_IS_RESULT_OF = URIRef("http://www.w3.org/ns/sosa/isResultOf")
SOSA_HAS_FOI = URIRef("http://www.w3.org/ns/sosa/hasFeatureOfInterest")
EMOBON_OBSERVATORY = URIRef("https://data.emobon.embrc.eu/ns/core#Observatory")

def subset_rdf_graph(
    workspace_dir: Path,
    output_dir: Path,
    qualifying_events: Set[str]
) -> Path:
    """
    Subsets all-triples.ttl into output_dir/all-triples.ttl containing only the subgraphs
    for qualifying_events, their samples, observations, blank nodes, and observatory info.
    """
    src_ttl = workspace_dir / "all-triples.ttl"
    out_ttl = output_dir / "all-triples.ttl"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not src_ttl.exists():
        # Create empty graph
        Graph().serialize(out_ttl, format="turtle")
        return out_ttl

    src_graph = Graph()
    src_graph.parse(src_ttl, format="turtle")

    sub_graph = Graph()
    # Copy namespaces
    for prefix, ns in src_graph.namespaces():
        sub_graph.bind(prefix, ns)

    # 1. Find target event URIs
    target_event_uris: Set[URIRef] = set()
    for s in src_graph.subjects():
        if isinstance(s, URIRef):
            s_str = str(s)
            for ev in qualifying_events:
                if s_str.endswith(f"/sampling-event/{ev}") or s_str.endswith(f"/{ev}"):
                    target_event_uris.add(s)

    nodes_to_traverse: Set[rdflib.term.Identifier] = set(target_event_uris)

    # 2. Find samples linked to target events: ?sample sosa:isResultOf ?event
    sample_uris: Set[URIRef] = set()
    for ev_uri in target_event_uris:
        for sample in src_graph.subjects(SOSA_IS_RESULT_OF, ev_uri):
            sample_uris.add(sample)
            nodes_to_traverse.add(sample)

    # 3. Find observations linked to samples: ?obs sosa:hasFeatureOfInterest ?sample
    for sample in sample_uris:
        for obs in src_graph.subjects(SOSA_HAS_FOI, sample):
            nodes_to_traverse.add(obs)

    # 4. Find observatory entity: ?obs a emobon-core:Observatory
    for obs_entity in src_graph.subjects(RDF.type, EMOBON_OBSERVATORY):
        nodes_to_traverse.add(obs_entity)

    # 5. Extract all outgoing triples and recursively extract blank nodes
    visited: Set[rdflib.term.Identifier] = set()
    queue = list(nodes_to_traverse)

    while queue:
        node = queue.pop()
        if node in visited:
            continue
        visited.add(node)

        for p, o in src_graph.predicate_objects(node):
            sub_graph.add((node, p, o))
            if isinstance(o, BNode) and o not in visited:
                queue.append(o)

    sub_graph.serialize(out_ttl, format="turtle")
    return out_ttl
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_subsetter.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add action/graph_subsetter.py tests/test_graph_subsetter.py
git commit -m "feat: implement RDF graph subsetter with rdflib"
```

---

### Task 5: Archive Packager (`action/packager.py`)

**Files:**
- Create: `action/packager.py`
- Test: `tests/test_packager.py`

**Interfaces:**
- Consumes: `output_dir: Path`, `mapping_rows: list[dict]`, `observatory: str`, `affix: str`
- Produces: `package_subset_archive(output_dir: Path, observatory: str, affix: str, mapping_rows: list[dict]) -> Path`
  Creates `<output_dir>/<observatory>_<affix>.zip`.

- [ ] **Step 1: Write the failing test for packager**

Create `tests/test_packager.py`:
```python
import zipfile
from pathlib import Path
from action.packager import package_subset_archive

def test_package_subset_archive(tmp_path: Path):
    stage_dir = tmp_path / "stage"
    stage_dir.mkdir()
    (stage_dir / "logsheets").mkdir()
    (stage_dir / "logsheets" / "sediment_sampling.csv").write_text("dummy,data\n1,2\n")
    (stage_dir / "all-triples.ttl").write_text("@prefix ex: <http://example.org/> .\n")

    mapping = [{"event_id": "EV1", "source_mat_id": "SM1", "ena_accession_number_run_metag": "ERR123"}]

    zip_path = package_subset_archive(stage_dir, "BPNS", "bluecloud-ENA", mapping)

    assert zip_path.exists()
    assert zip_path.name == "BPNS_bluecloud-ENA.zip"

    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert "logsheets/sediment_sampling.csv" in namelist
        assert "all-triples.ttl" in namelist
        assert "ena_accessions_subset.csv" in namelist
        assert "README.md" in namelist
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packager.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'action.packager'`.

- [ ] **Step 3: Write implementation in action/packager.py**

Create `action/packager.py`:
```python
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
import zipfile

def package_subset_archive(
    output_dir: Path,
    observatory: str,
    affix: str,
    mapping_rows: List[Dict[str, str]]
) -> Path:
    """
    Writes mapping CSV and README to output_dir and bundles everything into <observatory>_<affix>.zip.
    """
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
    readme_content = f"""# EMO BON Subsetted Distribution: {observatory} ({affix})

- **Date Published**: {today}
- **Observatory Station**: {observatory}
- **Affix / Purpose**: {affix} (Sequenced samples with ENA run accessions)
- **License**: Creative Commons Attribution 4.0 International (CC BY 4.0)

## Contents
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

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_packager.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add action/packager.py tests/test_packager.py
git commit -m "feat: implement archive packager"
```

---

### Task 6: Semantic Distribution Linker (`action/distribution_linker.py`)

**Files:**
- Create: `action/distribution_linker.py`
- Test: `tests/test_distribution_linker.py`

**Interfaces:**
- Consumes: `all-triples.ttl` in workspace, `repo_name: str`, `observatory: str`, `affix: str`, `download_url: str`
- Produces: `link_distribution_in_triples(workspace_dir: Path, repo_name: str, observatory: str, affix: str, download_url: str) -> None`

- [ ] **Step 1: Write the failing test for distribution linker**

Create `tests/test_distribution_linker.py`:
```python
from pathlib import Path
import rdflib
from action.distribution_linker import link_distribution_in_triples

INITIAL_TURTLE = """
@prefix schema: <https://schema.org/> .
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct: <http://purl.org/dc/terms/> .

<https://data.emobon.embrc.eu/observatory-bpns-crate> a schema:Dataset, dcat:Dataset ;
    dct:title "BPNS Observatory Dataset" .
"""

def test_link_distribution_in_triples(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ttl_file = workspace / "all-triples.ttl"
    ttl_file.write_text(INITIAL_TURTLE)

    download_url = "https://github.com/emo-bon/observatory-bpns-crate/releases/download/bluecloud-ENA-latest/BPNS_bluecloud-ENA.zip"
    link_distribution_in_triples(workspace, "emo-bon/observatory-bpns-crate", "BPNS", "bluecloud-ENA", download_url)

    g = rdflib.Graph()
    g.parse(ttl_file, format="turtle")

    dist_uri = rdflib.URIRef("https://data.emobon.embrc.eu/observatory-bpns-crate/distribution/bluecloud-ENA")
    assert (dist_uri, rdflib.RDF.type, rdflib.URIRef("http://www.w3.org/ns/dcat#Distribution")) in g
    assert (dist_uri, rdflib.RDF.type, rdflib.URIRef("https://schema.org/DataDownload")) in g
    assert (dist_uri, rdflib.URIRef("http://www.w3.org/ns/dcat#downloadURL"), rdflib.URIRef(download_url)) in g
    assert (dist_uri, rdflib.URIRef("https://schema.org/contentUrl"), rdflib.URIRef(download_url)) in g

    dataset_uri = rdflib.URIRef("https://data.emobon.embrc.eu/observatory-bpns-crate")
    assert (dataset_uri, rdflib.URIRef("http://www.w3.org/ns/dcat#distribution"), dist_uri) in g
    assert (dataset_uri, rdflib.URIRef("https://schema.org/distribution"), dist_uri) in g
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_distribution_linker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'action.distribution_linker'`.

- [ ] **Step 3: Write implementation in action/distribution_linker.py**

Create `action/distribution_linker.py`:
```python
from datetime import datetime, timezone
from pathlib import Path
import rdflib
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCAT, DCTERMS, RDF, XSD

SCHEMA = rdflib.Namespace("https://schema.org/")

def link_distribution_in_triples(
    workspace_dir: Path,
    repo_name: str,
    observatory: str,
    affix: str,
    download_url: str
) -> None:
    """
    Appends or updates dcat:Distribution & schema:DataDownload in workspace_dir/all-triples.ttl.
    """
    ttl_file = workspace_dir / "all-triples.ttl"
    g = Graph()
    if ttl_file.exists():
        g.parse(ttl_file, format="turtle")

    g.bind("dcat", DCAT)
    g.bind("dct", DCTERMS)
    g.bind("schema", SCHEMA)

    # Clean repo slug (e.g. "emo-bon/observatory-bpns-crate" -> "observatory-bpns-crate")
    repo_slug = repo_name.split("/")[-1]
    dataset_uri = URIRef(f"https://data.emobon.embrc.eu/{repo_slug}")
    dist_uri = URIRef(f"https://data.emobon.embrc.eu/{repo_slug}/distribution/{affix}")
    download_uriref = URIRef(download_url)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Remove existing distribution triples for this URI if re-running
    for p, o in list(g.predicate_objects(dist_uri)):
        g.remove((dist_uri, p, o))

    # Add distribution node
    g.add((dist_uri, RDF.type, DCAT.Distribution))
    g.add((dist_uri, RDF.type, SCHEMA.DataDownload))
    g.add((dist_uri, DCAT.downloadURL, download_uriref))
    g.add((dist_uri, SCHEMA.contentUrl, download_uriref))
    g.add((dist_uri, DCAT.mediaType, Literal("application/zip")))
    g.add((dist_uri, DCTERMS.title, Literal(f"{observatory} {affix} Distribution")))
    g.add((dist_uri, SCHEMA.name, Literal(f"{observatory} {affix} Distribution")))
    g.add((dist_uri, DCTERMS.issued, Literal(today, datatype=XSD.date)))
    g.add((dist_uri, SCHEMA.datePublished, Literal(today, datatype=XSD.date)))

    # Link from dataset
    g.add((dataset_uri, DCAT.distribution, dist_uri))
    g.add((dataset_uri, SCHEMA.distribution, dist_uri))

    g.serialize(ttl_file, format="turtle")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_distribution_linker.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add action/distribution_linker.py tests/test_distribution_linker.py
git commit -m "feat: implement distribution linker in all-triples.ttl"
```

---

### Task 7: GitHub Release Publisher (`action/release_publisher.py`)

**Files:**
- Create: `action/release_publisher.py`
- Test: `tests/test_release_publisher.py`

**Interfaces:**
- Produces: `publish_github_release(repo: str, token: str, tag: str, asset_path: Path, title: str, body: str) -> str`
  Returns download URL of uploaded asset.

- [ ] **Step 1: Write the failing test with mocked GitHub REST API**

Create `tests/test_release_publisher.py`:
```python
from pathlib import Path
from unittest.mock import MagicMock, patch
from action.release_publisher import publish_github_release

def test_publish_github_release_new(tmp_path: Path):
    asset_file = tmp_path / "BPNS_bluecloud-ENA.zip"
    asset_file.write_bytes(b"PK00mockzip")

    mock_resp_get = MagicMock()
    mock_resp_get.status_code = 404

    mock_resp_post = MagicMock()
    mock_resp_post.status_code = 201
    mock_resp_post.json.return_value = {
        "id": 12345,
        "upload_url": "https://uploads.github.com/repos/emo-bon/test/releases/12345/assets{?name,label}"
    }

    mock_resp_upload = MagicMock()
    mock_resp_upload.status_code = 201
    mock_resp_upload.json.return_value = {
        "browser_download_url": "https://github.com/emo-bon/test/releases/download/bluecloud-ENA-latest/BPNS_bluecloud-ENA.zip"
    }

    with patch("requests.get", return_value=mock_resp_get), \
         patch("requests.post", side_effect=[mock_resp_post, mock_resp_upload]):
        download_url = publish_github_release(
            repo="emo-bon/test",
            token="ghp_mocktoken",
            tag="bluecloud-ENA-latest",
            asset_path=asset_file,
            title="Release Title",
            body="Release Body"
        )

    assert "releases/download/bluecloud-ENA-latest/BPNS_bluecloud-ENA.zip" in download_url
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_release_publisher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'action.release_publisher'`.

- [ ] **Step 3: Write implementation in action/release_publisher.py**

Create `action/release_publisher.py`:
```python
import os
from pathlib import Path
import requests

def publish_github_release(
    repo: str,
    token: str,
    tag: str,
    asset_path: Path,
    title: str,
    body: str
) -> str:
    """
    Creates or updates a GitHub Release for the given tag and uploads asset_path.
    Returns the asset download URL.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    api_base = f"https://api.github.com/repos/{repo}"
    rel_res = requests.get(f"{api_base}/releases/tags/{tag}", headers=headers, timeout=30)

    if rel_res.status_code == 200:
        release_data = rel_res.json()
        release_id = release_data["id"]
        # Delete existing asset with same name if exists
        assets_res = requests.get(f"{api_base}/releases/{release_id}/assets", headers=headers, timeout=30)
        if assets_res.status_code == 200:
            for asset in assets_res.json():
                if asset["name"] == asset_path.name:
                    requests.delete(f"{api_base}/releases/assets/{asset['id']}", headers=headers, timeout=30)

        upload_url = release_data["upload_url"].split("{")[0]
    else:
        create_res = requests.post(
            f"{api_base}/releases",
            headers=headers,
            json={"tag_name": tag, "name": title, "body": body, "draft": False, "prerelease": False},
            timeout=30
        )
        create_res.raise_for_status()
        release_data = create_res.json()
        upload_url = release_data["upload_url"].split("{")[0]

    # Upload asset
    with open(asset_path, "rb") as f:
        upload_res = requests.post(
            upload_url,
            headers={**headers, "Content-Type": "application/zip"},
            params={"name": asset_path.name},
            data=f,
            timeout=120
        )
    upload_res.raise_for_status()
    return upload_res.json().get(
        "browser_download_url",
        f"https://github.com/{repo}/releases/download/{tag}/{asset_path.name}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_release_publisher.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add action/release_publisher.py tests/test_release_publisher.py
git commit -m "feat: implement GitHub Release upsert and asset upload"
```

---

### Task 8: CLI Entrypoint & Pipeline Orchestration (`action/main.py`)

**Files:**
- Create: `action/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Reads GitHub Action inputs/environment variables.
- Runs resource loader -> tabular subsetter -> graph subsetter -> packager -> release publisher -> distribution linker.
- Emits GitHub Action step outputs via `$GITHUB_OUTPUT`.

- [ ] **Step 1: Write integration test for main pipeline orchestration**

Create `tests/test_main.py`:
```python
import os
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'action.main'`.

- [ ] **Step 3: Write implementation in action/main.py**

Create `action/main.py`:
```python
import os
import sys
from pathlib import Path
from action.resource_loader import load_ena_qualifying_events, fetch_remote_resources
from action.tabular_subsetter import subset_logsheets
from action.graph_subsetter import subset_rdf_graph
from action.packager import package_subset_archive
from action.distribution_linker import link_distribution_in_triples
from action.release_publisher import publish_github_release

def set_action_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"::set-output name={name}::{value}")

def derive_observatory_name(repo_name: str, workspace_dir: Path) -> str:
    # E.g. "emo-bon/observatory-bpns-crate" -> "BPNS"
    slug = repo_name.split("/")[-1].lower()
    if "observatory-" in slug:
        parts = slug.split("observatory-")[1].split("-")
        return parts[0].upper()
    return "OBSERVATORY"

def run_pipeline(
    workspace_dir: Path,
    output_dir: Path,
    ena_records_url: str,
    remote_resources: str,
    distribution_affix: str,
    repo_name: str,
    token: str,
    create_release: bool
) -> dict:
    print(f"Loading ENA qualifying events from: {ena_records_url}")
    qualifying_events, mapping_rows = load_ena_qualifying_events(ena_records_url)
    print(f"Found {len(qualifying_events)} qualifying events with ENA run accessions.")

    if remote_resources:
        cache_dir = workspace_dir / ".subsetted_cache"
        fetch_remote_resources(remote_resources, cache_dir)

    observatory = derive_observatory_name(repo_name, workspace_dir)

    if not qualifying_events:
        print(f"No qualifying ENA events found for observatory {observatory}. Terminating cleanly.")
        return {
            "release_tag": f"{distribution_affix}-latest",
            "release_download_url": "",
            "subsetted_events_count": 0,
            "subsetted_samples_count": 0
        }

    # Tabular subsetting
    events_count, samples_count, sample_ids = subset_logsheets(workspace_dir, output_dir, qualifying_events)
    print(f"Subsetted tabular logsheets: {events_count} events, {samples_count} samples.")

    # RDF graph subsetting
    subset_rdf_graph(workspace_dir, output_dir, qualifying_events)
    print("Subsetted RDF graph generated in output directory.")

    # Packaging
    archive_path = package_subset_archive(output_dir, observatory, distribution_affix, mapping_rows)
    print(f"Packaged archive created: {archive_path.name}")

    release_tag = f"{distribution_affix}-latest"
    default_download_url = f"https://github.com/{repo_name}/releases/download/{release_tag}/{archive_path.name}"

    download_url = default_download_url
    if create_release and token:
        title = f"EMO BON Observatory {observatory} - {distribution_affix} Distribution"
        body = f"Automated subsetted distribution for EMO BON Observatory {observatory} containing events sequenced in ENA."
        print(f"Publishing release to GitHub with tag: {release_tag}")
        download_url = publish_github_release(repo_name, token, release_tag, archive_path, title, body)

    # Link in main repository's all-triples.ttl
    link_distribution_in_triples(workspace_dir, repo_name, observatory, distribution_affix, download_url)
    print(f"Distribution linked into main repository all-triples.ttl with downloadURL: {download_url}")

    return {
        "release_tag": release_tag,
        "release_download_url": download_url,
        "subsetted_events_count": events_count,
        "subsetted_samples_count": samples_count
    }

def main():
    workspace = Path(os.getenv("GITHUB_WORKSPACE", ".")).resolve()
    output_dir_name = os.getenv("INPUT_OUTPUT_DIR", "subsetted_distribution")
    output_dir = (workspace / output_dir_name).resolve()

    ena_records_url = os.getenv(
        "INPUT_ENA_RECORDS_URL",
        "https://raw.githubusercontent.com/emo-bon/sequencing-logistics-crate/main/ena-accession-numbers-batches1-2.csv"
    )
    remote_resources = os.getenv("INPUT_REMOTE_RESOURCES", "")
    distribution_affix = os.getenv("INPUT_DISTRIBUTION_AFFIX", "bluecloud-ENA")
    create_release = os.getenv("INPUT_CREATE_RELEASE", "true").lower() in ("true", "1", "yes")
    token = os.getenv("INPUT_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN", "")
    repo_name = os.getenv("INPUT_GITHUB_REPOSITORY") or os.getenv("GITHUB_REPOSITORY", "emo-bon/observatory")

    outputs = run_pipeline(
        workspace_dir=workspace,
        output_dir=output_dir,
        ena_records_url=ena_records_url,
        remote_resources=remote_resources,
        distribution_affix=distribution_affix,
        repo_name=repo_name,
        token=token,
        create_release=create_release
    )

    for k, v in outputs.items():
        set_action_output(k, str(v))

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add action/main.py tests/test_main.py
git commit -m "feat: implement main action pipeline entrypoint"
```

---

### Task 9: BPNS Real-World Workflow End-to-End Verification

**Files:**
- Create: `tests/test_bpns_workflow_e2e.py`
- Create: `.github/workflows/test-bpns-workflow.yml`

**Interfaces:**
- Runs the full pipeline against real BPNS data (fetching real `BPNS_So_210726` and `ERR13955095` samples).
- Verifies that `BPNS_bluecloud-ENA.zip` is created, contains `logsheets/sediment_sampling.csv`, `all-triples.ttl`, `ena_accessions_subset.csv`, and that the root `all-triples.ttl` is updated with `dcat:Distribution`.

- [ ] **Step 1: Write tests/test_bpns_workflow_e2e.py**

```python
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

    # Fetch real BPNS transformed logsheets and all-triples slice
    base_url = "https://raw.githubusercontent.com/emo-bon/observatory-bpns-crate/main"
    for filename in ["sediment_sampling.csv", "sediment_measured.csv", "sediment_observatory.csv"]:
        try:
            content = urllib.request.urlopen(f"{base_url}/logsheets/transformed/{filename}", timeout=30).read()
            (logsheets_dir / filename).write_bytes(content)
        except Exception:
            pass

    # Fetch real all-triples.ttl
    ttl_content = urllib.request.urlopen(f"{base_url}/all-triples.ttl", timeout=60).read()
    (workspace / "all-triples.ttl").write_bytes(ttl_content)

    # Run full pipeline with real ENA batches 1-2 CSV
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
```

- [ ] **Step 2: Create GitHub Actions Workflow for automated CI testing**

Create `.github/workflows/test-bpns-workflow.yml`:
```yaml
name: Test BPNS Workflow Integration

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Action Repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Dependencies
        run: pip install -r requirements.txt

      - name: Run Test Suite (Unit & BPNS Integration)
        run: pytest -v
```

- [ ] **Step 3: Run pytest to verify all unit and integration tests pass**

Run: `pytest -v`
Expected: ALL PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_bpns_workflow_e2e.py .github/workflows/test-bpns-workflow.yml
git commit -m "test: add BPNS real-world end-to-end workflow verification"
```
