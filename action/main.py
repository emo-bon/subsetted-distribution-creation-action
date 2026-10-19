import os
import sys
from pathlib import Path

# Ensure package directory is in sys.path regardless of current working directory
_pkg_root = str(Path(__file__).resolve().parent.parent)
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from action.resource_loader import load_ena_qualifying_events, fetch_remote_resources, load_observatories_governance
from action.tabular_subsetter import subset_logsheets
from action.graph_subsetter import subset_rdf_graph
from action.metadata_extractor import extract_distribution_metadata
from action.ro_crate_builder import build_ro_crate
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
    create_release: bool,
    observatories_url: str = "https://raw.githubusercontent.com/emo-bon/governance-crate/main/observatories.csv"
) -> dict:
    print(f"Loading ENA qualifying events from: {ena_records_url}")
    qualifying_events, mapping_rows = load_ena_qualifying_events(ena_records_url)
    print(f"Found {len(qualifying_events)} qualifying events with ENA run accessions.")

    cache_dir = workspace_dir / ".subsetted_cache"
    if remote_resources:
        fetch_remote_resources(remote_resources, cache_dir)

    print(f"Loading observatories governance metadata from: {observatories_url}")
    observatories_info = load_observatories_governance(observatories_url, cache_dir)

    observatory = derive_observatory_name(repo_name, workspace_dir)

    if not qualifying_events:
        print(f"No qualifying ENA events found for observatory {observatory}. Terminating cleanly.")
        return {
            "release_tag": f"{distribution_affix}-latest",
            "release_download_url": "",
            "rocrate_metadata_url": "",
            "subsetted_events_count": 0,
            "subsetted_samples_count": 0
        }

    # Tabular subsetting
    events_count, samples_count, sample_ids = subset_logsheets(workspace_dir, output_dir, qualifying_events)
    print(f"Subsetted tabular logsheets: {events_count} events, {samples_count} samples.")

    # RDF graph subsetting
    subset_rdf_graph(workspace_dir, output_dir, qualifying_events)
    print("Subsetted RDF graph generated in output directory.")

    # RO-Crate metadata extraction & building
    metadata = extract_distribution_metadata(
        workspace_dir=workspace_dir,
        output_dir=output_dir,
        observatory_id=observatory,
        governance_mapping=observatories_info,
        repo_name=repo_name,
        distribution_affix=distribution_affix
    )
    crate_path = build_ro_crate(output_dir, metadata)

    print(f"RO-Crate metadata descriptor generated: {crate_path.name}")

    # Packaging
    citation_text = metadata.get("citation_text", "")
    archive_path = package_subset_archive(output_dir, observatory, distribution_affix, mapping_rows, citation_text=citation_text)
    print(f"Packaged archive created: {archive_path.name}")

    release_tag = f"{distribution_affix}-latest"
    default_download_url = f"https://github.com/{repo_name}/releases/download/{release_tag}/{archive_path.name}"
    default_rocrate_url = f"https://github.com/{repo_name}/releases/download/{release_tag}/{crate_path.name}"

    download_url = default_download_url
    rocrate_url = default_rocrate_url
    if create_release and token:
        title = f"EMO BON Observatory {observatory} - {distribution_affix} Distribution"
        body = f"Automated subsetted distribution for EMO BON Observatory {observatory} containing events sequenced in ENA."
        print(f"Publishing release to GitHub with tag: {release_tag}")
        upload_res = publish_github_release(repo_name, token, release_tag, [archive_path, crate_path], title, body)
        if isinstance(upload_res, dict):
            download_url = upload_res.get(archive_path.name, default_download_url)
            rocrate_url = upload_res.get(crate_path.name, default_rocrate_url)
        else:
            download_url = upload_res

    # Link in main repository's all-triples.ttl
    link_distribution_in_triples(
        workspace_dir,
        repo_name,
        observatory,
        distribution_affix,
        download_url,
        metadata_url=rocrate_url
    )
    print(f"Distribution linked into main repository all-triples.ttl with downloadURL: {download_url} and metadataURL: {rocrate_url}")

    return {
        "release_tag": release_tag,
        "release_download_url": download_url,
        "rocrate_metadata_url": rocrate_url,
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
    observatories_url = os.getenv(
        "INPUT_OBSERVATORIES_URL",
        "https://raw.githubusercontent.com/emo-bon/governance-crate/main/observatories.csv"
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
        create_release=create_release,
        observatories_url=observatories_url
    )

    for k, v in outputs.items():
        set_action_output(k, str(v))


if __name__ == "__main__":
    main()
