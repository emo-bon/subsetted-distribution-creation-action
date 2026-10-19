import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
import zipfile

def package_subset_archive(
    output_dir: Path,
    observatory: str,
    affix: str,
    mapping_rows: List[Dict[str, str]],
    citation_text: str = ""
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
