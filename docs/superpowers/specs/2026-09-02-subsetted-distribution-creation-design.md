# Specification: Subsetted Distribution Creation Action

- **Date**: 2026-09-02
- **Repository**: `emo-bon/subsetted-distribution-creation-action`
- **Target Integration**: EMO BON Observatory repositories (e.g., `emo-bon/observatory-bpns-crate`)
- **Primary Aggregator**: Blue-Cloud (and future aggregators)

---

## 1. Background & Purpose

The European Marine Omics Biodiversity Observation Network (EMO BON) maintains observatory repositories containing raw and curated sampling logsheets (CSVs) and semantic triples (`all-triples.ttl`). External aggregators like Blue-Cloud harvest datasets from these observatories. However, Blue-Cloud requires distributions that only include sampling events and measurements for which genomic sequences are publicly available in the European Nucleotide Archive (ENA).

Until the sequencing crate is fully triplised, an ENA accession mapping file (created in `emo-bon/sequencing-logistics-crate#27`) links sample IDs (`source_mat_id`), sampling events (`event_id`), and ENA run accessions (`ena_accession_number_run_metag`).

This GitHub Action:
1. Identifies qualifying sampling events with valid ENA run accession numbers.
2. Subsets the tabular logsheets (`sampling.csv`, `measured.csv`, preserving `observatory.csv`) for all habitats (`water`, `sediment`, `hard`).
3. Subsets the semantic RDF graph (`all-triples.ttl`) for all matching events, samples, observations, observatory details, and auxiliary blank nodes.
4. Packages these subsetted files into a compressed release asset named `<observatory>_<affix>.zip`.
5. Creates or updates a GitHub Release using a stable floating tag (`<affix>-latest`) to provide permanent download URLs for aggregators.
6. Links the distribution into the observatory repository's root `all-triples.ttl` with `dcat:Distribution` and `schema:DataDownload` semantic metadata.

---

## 2. Architecture & Container Interface

### 2.1 Action Packaging
Following existing EMO BON conventions (`populate-action`, `semantic-uplifting-action`), this repository is packaged as a Docker-based GitHub Action:
- `action.yml`: Metadata definition, inputs, outputs, and docker runs configuration.
- `Dockerfile`: Debian-based container (`python:3.11-slim`) with `rdflib`, `requests`, `pyyaml`, and `pytest`.
- `entrypoint.sh`: Entrypoint running the Python action module.
- `action/`: Python package containing modular logic.
- `tests/`: Automated unit and integration tests.

### 2.2 Inputs & Environment Variables

| Name | Required | Default | Description |
|---|---|---|---|
| `ena_records_url` | No | `https://raw.githubusercontent.com/emo-bon/sequencing-logistics-crate/main/ena-accession-numbers-batches1-2.csv` | Remote URL pointing to the ENA run accessions CSV. |
| `remote_resources` | No | `""` | Optional YAML or JSON string specifying additional remote key-value URLs or resources to fetch. |
| `distribution_affix` | No | `bluecloud-ENA` | Identifier affix appended to the observatory name for the release tag and asset filename. |
| `output_dir` | No | `subsetted_distribution` | Local workspace directory where subsetted artifacts are staged. |
| `create_release` | No | `true` | Boolean flag. When `false`, release publishing is skipped (useful for local runs/tests). |
| `github_token` / `GITHUB_TOKEN` | Yes (for release) | `${{ github.token }}` | GitHub token with `contents: write` permission to create/update releases. |
| `github_repository` / `GITHUB_REPOSITORY` | Yes | `${{ github.repository }}` | Target repository in `owner/repo` format. |
| `github_workspace` / `GITHUB_WORKSPACE` | Yes | `${{ github.workspace }}` | Workspace root directory inside the runner. |

### 2.3 Outputs

| Name | Description | Example |
|---|---|---|
| `release_tag` | Tag name created or updated | `bluecloud-ENA-latest` |
| `release_download_url` | Direct download URL of the uploaded archive asset | `https://github.com/emo-bon/observatory-bpns-crate/releases/download/bluecloud-ENA-latest/BPNS_bluecloud-ENA.zip` |
| `subsetted_events_count` | Number of unique `event_id`s in the subset | `14` |
| `subsetted_samples_count` | Number of sample IDs included in the subset | `42` |

---

## 3. Detailed Component Design

### 3.1 Remote Resource Loader (`action/resource_loader.py`)
- **Purpose**: Ingests remote data safely without colliding with existing workspace files.
- **Workflow**:
  1. Downloads `ena_records_url` with timeout and stream buffering.
  2. Parses the CSV and filters for rows where `ena_accession_number_run_metag` is non-empty after whitespace stripping.
  3. Extracts a set of unique `event_id` values (e.g. `{'BPNS_So_210726', ...}`).
  4. Generates an `ena_accessions_subset.csv` file mapping `event_id`, `source_mat_id`, and `ena_accession_number_run_metag` for inclusion in the release package.
  5. If `remote_resources` is supplied, parses YAML/JSON key-values and fetches each resource into `.subsetted_cache/<key>` for supplementary processing.

### 3.2 Tabular Subsetter (`action/tabular_subsetter.py`)
- **Purpose**: Subsets the logsheet CSV files accurately.
- **Input Directory**: Checks `logsheets/transformed/` first; falls back to `logsheets/raw/` if `transformed` is not present.
- **Process per Habitat** (`water`, `sediment`, `hard`):
  1. **Sampling (`{habitat}_sampling.csv`)**:
     - Reads all rows using Python `csv.DictReader` preserving column order.
     - Selects rows where `sampling_event` is in the qualifying `event_id` set.
     - Collects all `source_mat_id` and `source_mat_id_orig` identifiers from the selected rows. Because replicates and blanks share the same `sampling_event`, they are automatically retained.
     - Writes retained rows using `csv.DictWriter` to `<output_dir>/logsheets/{habitat}_sampling.csv`.
  2. **Measured (`{habitat}_measured.csv`)**:
     - Reads all rows.
     - Selects rows where `source_mat_id` or `source_mat_id_orig` exists in the collected sample identifiers set.
     - Writes retained rows to `<output_dir>/logsheets/{habitat}_measured.csv`.
  3. **Observatory (`{habitat}_observatory.csv`)**:
     - Copied entirely to `<output_dir>/logsheets/{habitat}_observatory.csv` to preserve observatory station metadata.

### 3.3 Graph Subsetter (`action/graph_subsetter.py`)
- **Purpose**: Extracts a self-contained RDF subgraph representing only the subsetted events.
- **Source**: `all-triples.ttl` in the repository root.
- **Algorithm**:
  1. Parses `all-triples.ttl` using `rdflib.Graph()`.
  2. Resolves Observatory ID (e.g. `BPNS`) from repository name or `?obs a emobon-core:Observatory`.
  3. Identifies target event URIs whose URI path ends with `/sampling-event/{event_id}` for each qualifying `event_id`.
  4. Collects:
     - All triples where the event URI is the subject.
     - All sample URIs linked via `?sample sosa:isResultOf ?eventURI`.
     - All triples where each sample URI is the subject.
     - All observation URIs linked via `?obs sosa:hasFeatureOfInterest ?sampleURI`.
     - All triples where each observation URI is the subject.
     - The observatory entity URI and its outgoing triples (name, location, organization).
     - Auxiliary blank nodes: recursively traverses any blank node referenced in objects of collected triples and includes their predicates and objects.
  5. Serializes the extracted subgraph to `<output_dir>/all-triples.ttl` in Turtle format with all standard EMO BON namespace prefixes preserved.

### 3.4 Packaging Engine (`action/packager.py`)
- **Purpose**: Bundles the subsetted files into a standard archive.
- **Archive Path**: `<output_dir>/<observatory>_<affix>.zip` (e.g. `BPNS_bluecloud-ENA.zip`).
- **Archive Contents**:
  - `logsheets/*.csv`: The subsetted tabular files.
  - `all-triples.ttl`: The subsetted semantic graph.
  - `ena_accessions_subset.csv`: ENA accession mapping table.
  - `README.md`: Auto-generated summary explaining the subset parameters, date published, license (CC-BY 4.0), and link to source observatory crate.

### 3.5 GitHub Release Publisher (`action/release_publisher.py`)
- **Purpose**: Creates or updates a GitHub Release and uploads the archive asset.
- **Mechanism**: GitHub REST API (`https://api.github.com/repos/<owner>/<repo>/releases`):
  1. Checks if a release already exists for tag `<affix>-latest`.
  2. If found:
     - Updates release title and body description.
     - Checks existing release assets: if `<observatory>_<affix>.zip` already exists, deletes the previous asset.
     - Uploads the new `<observatory>_<affix>.zip` binary to the release asset endpoint (`https://uploads.github.com/...`).
  3. If not found:
     - Creates a new release pointing to `target_commitish = HEAD` with tag `<affix>-latest`.
     - Uploads `<observatory>_<affix>.zip` as a release asset.
  4. Constructs direct download URL:
     `https://github.com/<owner>/<repo>/releases/download/<affix>-latest/<observatory>_<affix>.zip`.

### 3.6 Semantic Distribution Linker (`action/distribution_linker.py`)
- **Purpose**: Updates the main repository's `all-triples.ttl` with semantic distribution metadata.
- **Workflow**:
  1. Loads the main repository's `all-triples.ttl`.
  2. Identifies the primary Dataset URI (e.g., `https://data.emobon.embrc.eu/<repo-name>`). If not present, creates the Dataset entity representing the repository.
  3. Defines distribution node:
     `<https://data.emobon.embrc.eu/<repo-name>/distribution/<affix>>`
  4. Adds or updates predicates:
     - `rdf:type`: `dcat:Distribution`, `schema:DataDownload`
     - `dcat:downloadURL`: `<download_url>`
     - `schema:contentUrl`: `<download_url>`
     - `dcat:mediaType`: `"application/zip"`
     - `dct:title`: `"<observatory> <affix> Distribution"`
     - `schema:name`: `"<observatory> <affix> Distribution"`
     - `dct:issued`: Current ISO date literal (`xsd:date`)
     - `schema:datePublished`: Current ISO date literal (`xsd:date`)
  5. Links Dataset:
     - `?dataset dcat:distribution <distribution_node>`
     - `?dataset schema:distribution <distribution_node>`
  6. Serializes the updated graph back to `all-triples.ttl` in the repository root.

---

## 4. Error Handling & Edge Cases

1. **No Qualifying Events Found**:
   - If an observatory has no samples with ENA run accessions yet, the action logs:
     `"No qualifying events with ENA run accessions found for observatory <name>. Skipping distribution release."`
   - The step terminates cleanly with exit code 0 so the scheduled workflow does not fail.
2. **Missing Habitat Files**:
   - If an observatory only samples `water` (no `sediment` or `hard`), the tabular subsetter processes existing files without error.
3. **Invalid or Missing GitHub Token**:
   - Validates that `GITHUB_TOKEN` is present when `create_release=true`. Emits clear diagnostic instructions if HTTP 401 or 403 occurs.
4. **Network Resiliency**:
   - Implements exponential backoff retries for remote resource downloading and asset upload.

---

## 5. Verification & Testing Plan

### 5.1 Unit Tests (`pytest tests/`)
- `test_resource_loader.py`:
  - Validates filtering of non-empty `ena_accession_number_run_metag`.
  - Verifies extraction of unique `event_id` sets.
  - Verifies parsing of extra `remote_resources`.
- `test_tabular_subsetter.py`:
  - Validates row filtering on mock `sampling.csv`, `measured.csv`, and `observatory.csv`.
  - Confirms replicates and blanks sharing `sampling_event` are retained.
- `test_graph_subsetter.py`:
  - Loads a test Turtle graph with sampling events, samples, observations, blank nodes, and unrelated events.
  - Asserts that only qualifying subgraphs and blank nodes are in the subsetted graph.
- `test_distribution_linker.py`:
  - Verifies that `dcat:Distribution` and `schema:DataDownload` triples are properly injected into an existing `all-triples.ttl` without altering unrelated triples.
- `test_packager.py`:
  - Verifies zip structure, filenames, and README presence.
- `test_release_publisher.py`:
  - Uses `unittest.mock` to verify GitHub API requests for release upserting and asset replacement.

### 5.2 End-to-End Integration Verification
- Using BPNS test data (`BPNS_So_210726` and `ERR13955095`):
  - Run the full pipeline with `create_release: false`.
  - Verify that the resulting zip archive contains:
    - `logsheets/sediment_sampling.csv` with matching rows.
    - `logsheets/sediment_measured.csv` with matching samples.
    - `all-triples.ttl` containing the extracted subgraphs.
    - `ena_accessions_subset.csv`.
  - Verify that the root `all-triples.ttl` is updated with valid distribution triples.
