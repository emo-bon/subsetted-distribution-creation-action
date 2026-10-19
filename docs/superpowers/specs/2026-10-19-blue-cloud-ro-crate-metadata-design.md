# Design Specification: Blue Cloud RO-Crate Metadata Generation

- **Date**: 2026-10-19
- **Status**: Approved
- **Issue**: [emo-bon/subsetted-distribution-creation-action#1](https://github.com/emo-bon/subsetted-distribution-creation-action/issues/1)
- **Parent Discussion**: [emo-bon/emo-bon.github.io#39](https://github.com/emo-bon/emo-bon.github.io/issues/39)

---

## 1. Objective

Enable `subsetted-distribution-creation-action` to generate a standard, compliant RO-Crate 1.2 metadata record (`ro-crate-metadata.json`) using [`pysema`](https://github.com/vliz-be-opsci/py-sema) (`sema.ro.creator.ROCreator`). This metadata record fulfills Blue-Cloud catalog harvesting requirements (Level 1 metadata record) for EMO BON observatory subsetted distributions.

The action will:
1. Aggregate metadata from subsetted tabular logsheets, subsetted RDF triples, and governance data (`observatories.csv`).
2. Generate `ro-crate-metadata.json` via a blueprint YAML template and `ROCreator`.
3. Include `ro-crate-metadata.json` inside the distribution archive (`<observatory>_<affix>.zip`).
4. Publish `ro-crate-metadata.json` as an independent standalone asset in the GitHub Release alongside the `.zip` archive.
5. Link the distribution and metadata descriptor within the repository's root `all-triples.ttl`.

---

## 2. Requirements & Data Mapping

### 2.1 Governance Metadata (`observatories.csv`)
* **Source**: Remote CSV specified by the action input `observatories_url` (default: `https://raw.githubusercontent.com/emo-bon/governance-crate/main/observatories.csv`).
* **Lookup**: Matches the observatory identifier (e.g. `BPNS`, `VB`, `ROSKOGO`) against column `EMOBON_observatory_id`.
* **Resolved Values**:
  * `XXX` = `EMOBON_observatory_name` (e.g. `EMOBON-BE`).
  * `CCC` = `country` (e.g. `Belgium`).
  * Fallback coordinates: `water_site_latitude`, `water_site_longitude`, `sediment_site_latitude`, etc.
* **Fallback Behavior**: If network fails or the observatory code is unlisted in `observatories.csv`, defaults to the repository observatory code (`XXX = observatory_code`, `CCC = ""` or extracted from `logsheets/*_observatory.csv`).

### 2.2 Dataset Attributes
* **Title (`name`)**:
  `"Marine genomic sampling metadata from EMO BON Observation Network [station {XXX}; {CCC}]"`
* **Description**:
  Interpolates `XXX` and dynamic habitat text `YYY` into the standardized EMO BON Blue-Cloud text:
  > *"Here you will find all the data collected from the log sheets produced by the European Marine Omics Biodiversity Observation Network (EMO BON) observatory {XXX} for their {YYY} sampling activities. Log sheets are filled by the observatory during and after their sampling event, and every few months they are harvested, curated, and processed. The samples are sent for genomics processing: the raw genomic data can be found in ENA under PRJEB51688. The download from this metadata record is a copy of the sampling log sheets for all events for which sequences are available in ENA. It also includes a link to the website where you can find additional information and browse all other data."*
  * Dynamic `YYY`:
    * Water only $\rightarrow$ `"water"`
    * Sediment only $\rightarrow$ `"sediment"`
    * Hard only $\rightarrow$ `"hard-bottom"`
    * Water + Sediment $\rightarrow$ `"water, sediment"`
    * Water + Sediment + Hard $\rightarrow$ `"water, sediment, and hard-bottom"`
* **License**: `https://creativecommons.org/licenses/by/4.0/` (Creative Commons Attribution 4.0 International).
* **Citation**:
  `"European Marine Biological Research Centre (EMBRC), European Marine Omics Biodiversity Observation Network (EMO BON), Metadata logsheets for {TITLE}, {YEAR}, {REPO_LANDING_URL}, emobon@embrc.eu"`
* **Publisher / Project**:
  EMO BON (`https://www.embrc.eu/emo-bon/`).
* **Date Published & Date Modified (Datestamp)**:
  Current UTC date formatted as `YYYY-MM-DD`. `dateModified` serves as the record datestamp.
* **Identifier & URL**:
  * `url`: `https://data.emobon.embrc.eu/{repo_slug}/`
  * `identifier`: Array containing `https://data.emobon.embrc.eu/{repo_slug}/` and `https://github.com/{repo_name}/releases/tag/{release_tag}`.

### 2.3 Spatial Coverage
* Dynamically computed across retained rows in `sampling.csv` logsheets:
  * `min_lat = min(latitude)`
  * `min_lon = min(longitude)`
  * `max_lat = max(latitude)`
  * `max_lon = max(longitude)`
* Represented as a `schema:Place` with `geo:GeoShape`:
  * `box`: `"{min_lat} {min_lon} {max_lat} {max_lon}"`
* Falls back to site coordinates from `observatories.csv` if tabular coordinates are unavailable.

### 2.4 Temporal Coverage
* Dynamically computed across retained rows in `sampling.csv` logsheets:
  * `min_date = min(event_date)`
  * `max_date = max(event_date)`
* Formatted as ISO 8601 interval: `"{min_date}/{max_date}"`.
* `startDate`: `min_date`
* `endDate`: `max_date`

### 2.5 Keywords & Categories
* Literal keywords list:
  * `"marine genomics"`
  * `"European Marine Omics Biodiversity Observation Network"`
  * `"EMO BON"`
  * `"Biota"`
  * `"{OBSERVATORY_NAME}"`
* Biota Topic Category (DefinedTerm):
  * `@id`: `https://inspire.ec.europa.eu/metadata-codelist/TopicCategory/biota`
  * `@type`: `DefinedTerm`
  * `name`: `"Biota"`
  * `inDefinedTermSet`: `https://inspire.ec.europa.eu/metadata-codelist/TopicCategory`

### 2.6 Parameters (`variableMeasured`)
* Extracted from `sosa:Observation` entities in the subsetted graph:
  * Literal name: `rdfs:label`
  * Ontology URI: `dct:identifier` (if present)
* Represented as `schema:PropertyValue` nodes linked in `variableMeasured`:
  * `name`: parameter label
  * `propertyID`: ontology URI (if available)

### 2.7 Instruments
* Extracted from `schema:measurementTechnique` on observations and `schema:instrument` on sampling events.
* Recorded as string literals on the root dataset's `instrument` array.

### 2.8 Organizations
* Extracted from `organization` and `organization_edmoid` in `logsheets/*_observatory.csv`.
* Semicolon-delimited values (e.g. in BPNS) are split, matched, and deduplicated across all habitats.
* Each organization is assigned an entity:
  * `@id`: `https://edmo.seadatanet.org/report/{organization_edmoid}`
  * `@type`: `Organization`
  * `name`: organization name
  * `url`: `https://edmo.seadatanet.org/report/{organization_edmoid}`

---

## 3. Architecture & Component Changes

```
subsetted-distribution-creation-action/
├── action/
│   ├── blueprints/
│   │   └── bluecloud_ro_blueprint.yml     # RO-Crate 1.2 template for pysema
│   ├── distribution_linker.py             # Injects dcat:Distribution in root all-triples.ttl
│   ├── graph_subsetter.py                 # Extracts RDF subgraphs for qualifying events
│   ├── main.py                            # Action orchestrator and entrypoint
│   ├── metadata_extractor.py              # Computes spatial, temporal, param, and governance data
│   ├── packager.py                        # Bundles distribution .zip archive
│   ├── release_publisher.py               # Publishes GitHub release with .zip and ro-crate-metadata.json
│   ├── resource_loader.py                 # Loads ENA accessions and observatories.csv
│   ├── ro_crate_builder.py                # Wrapper around sema.ro.creator.ROCreator
│   └── tabular_subsetter.py               # Filters sampling and measured logsheet CSVs
├── action.yml                             # Action inputs and outputs definition
├── Dockerfile                             # Container image setup with pysema
└── requirements.txt                       # Python dependencies (pysema, rdflib, pyyaml, etc.)
```

### 3.1 Module Responsibilities

1. **`action/resource_loader.py`**:
   * Add `load_observatories_governance(url: str, cache_dir: Path) -> Dict[str, Dict[str, str]]` to fetch and parse `observatories.csv`.
2. **`action/metadata_extractor.py`**:
   * Inspects `output_dir/logsheets/` and `output_dir/all-triples.ttl`.
   * Aggregates spatial bounds, temporal intervals, parameters, instruments, organizations, and description texts.
3. **`action/blueprints/bluecloud_ro_blueprint.yml`**:
   * RO-Crate 1.2 blueprint parsed by `sema.ro.creator.ROCreator`.
4. **`action/ro_crate_builder.py`**:
   * Prepares the blueprint environment dictionary and dynamic entities.
   * Runs `ROCreator(blueprint_path=..., blueprint_env=..., rocrate_path=output_dir).process()`.
   * Produces `output_dir/ro-crate-metadata.json`.
5. **`action/packager.py`**:
   * Ensures `ro-crate-metadata.json` is packaged into `<observatory>_<affix>.zip`.
6. **`action/release_publisher.py`**:
   * Accepts multiple asset paths (`[archive_path, rocrate_metadata_path]`) and uploads both to the release.
7. **`action/distribution_linker.py`**:
   * Links both the archive download URL and metadata URL in the root `all-triples.ttl`.

### 3.2 Action Inputs & Outputs (`action.yml`)
* **New Input**:
  * `observatories_url`: Default `https://raw.githubusercontent.com/emo-bon/governance-crate/main/observatories.csv`.
* **New Output**:
  * `rocrate_metadata_url`: Direct download URL for `ro-crate-metadata.json`.

---

## 4. Verification & Testing Plan

1. **Unit Tests**:
   * `tests/test_resource_loader.py`: Test `load_observatories_governance` parsing and network fallback.
   * `tests/test_metadata_extractor.py`: Test bounding box calculations, temporal intervals, parameter deduplication, and organization EDMO mapping.
   * `tests/test_ro_crate_builder.py`: Test `ROCreator` execution and validate that `ro-crate-metadata.json` is created with valid JSON-LD structure matching RO-Crate 1.2 context.
2. **End-to-End Workflow Test**:
   * `tests/test_bpns_workflow_e2e.py`: Run complete pipeline simulating BPNS repository data; verify that:
     * `ro-crate-metadata.json` is generated with correct title, description, bounding box, parameters, organizations, and license.
     * `ro-crate-metadata.json` is inside `BPNS_bluecloud-ENA.zip`.
     * Standalone asset is tracked for GitHub Release upload.
     * Root `all-triples.ttl` is updated with distribution triples.
