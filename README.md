# subsetted-distribution-creation-action

GitHub Action responsible for creating subsetted distributions of EMO BON data that will be used to create artifacts. These distributions are created and maintained to comply with different aggregators (such as Blue-Cloud) by extracting only the sampling events, measurements, and triples linked to sequencing runs published in the European Nucleotide Archive (ENA).

---

## How It Works

1. **ENA Record Ingestion**: Downloads the ENA run accessions mapping (default from `emo-bon/sequencing-logistics-crate#27`) and extracts all sampling events with active ENA run accessions (`ena_accession_number_run_metag`).
2. **Tabular Subsetting**: Subsets `sampling.csv` and `measured.csv` logsheets (preserving `observatory.csv`) for all habitats (`water`, `sediment`, `hard`), including all replicates and blanks tied to matching sampling events.
3. **Graph Subsetting**: Parses `all-triples.ttl` with `rdflib` and extracts the complete subgraphs for matching sampling events, samples (`sosa:isResultOf`), observations (`sosa:hasFeatureOfInterest`), observatory station, and transitive blank nodes.
4. **Packaging**: Bundles the subsetted files into `<observatory>_<affix>.zip` (e.g. `BPNS_bluecloud-ENA.zip`) along with an ENA mapping summary (`ena_accessions_subset.csv`) and citation metadata (`README.md`).
5. **GitHub Release**: Upserts a GitHub Release using a stable floating tag (`<affix>-latest`, e.g. `bluecloud-ENA-latest`), replacing existing assets so aggregators have a fixed, permanent harvest URL.
6. **Semantic Linking**: Injects `dcat:Distribution` and `schema:DataDownload` metadata into the repository's root `all-triples.ttl` pointing to the release download URL.

---

## Usage in Observatory Repositories

Add this step to your observatory crate workflow (e.g. `.github/workflows/workflow.yml`):

```yaml
    - name: subsetted-distribution-creation-action
      uses: emo-bon/subsetted-distribution-creation-action@main
      with:
        distribution_affix: bluecloud-ENA
        github_token: ${{ secrets.GITHUB_TOKEN }}

    - name: git-auto-commit-action
      uses: stefanzweifel/git-auto-commit-action@v5
      with:
        commit_message: update all-triples.ttl with subsetted distribution
```

---

## Inputs

| Input | Description | Required | Default |
|---|---|---|---|
| `ena_records_url` | Remote URL pointing to the ENA run accessions CSV | No | `https://raw.githubusercontent.com/emo-bon/sequencing-logistics-crate/main/ena-accession-numbers-batches1-2.csv` |
| `remote_resources` | Optional YAML/JSON string specifying additional remote key-value URLs to fetch | No | `""` |
| `distribution_affix` | Affix appended to the observatory name for the release tag and asset filename | No | `bluecloud-ENA` |
| `output_dir` | Local workspace staging directory for subsetted artifacts | No | `subsetted_distribution` |
| `create_release` | Whether to publish or update the GitHub Release | No | `true` |
| `github_token` | GitHub token with `contents: write` permission to create/update releases | No | `${{ github.token }}` |

## Outputs

| Output | Description |
|---|---|
| `release_tag` | Release tag created or updated (e.g. `bluecloud-ENA-latest`) |
| `release_download_url` | Direct download URL for the archive asset |
| `subsetted_events_count` | Number of qualifying sampling events in the subset |
| `subsetted_samples_count` | Number of sample IDs included in the subset |

---

## Testing

Run the test suite locally:

```bash
pip install -r requirements.txt
pytest -v
```
