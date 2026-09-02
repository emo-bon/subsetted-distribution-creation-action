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

    retained_sample_lookup_ids: Set[str] = set()
    retained_samples: Set[str] = set()
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
                        primary_id = sm_id or sm_orig
                        if primary_id:
                            retained_samples.add(primary_id)
                        if sm_id:
                            retained_sample_lookup_ids.add(sm_id)
                            habitat_sample_ids.add(sm_id)
                        if sm_orig:
                            retained_sample_lookup_ids.add(sm_orig)
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

    return len(retained_events), len(retained_samples), retained_sample_lookup_ids
