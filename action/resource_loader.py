import csv
import io
import json
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
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
        req = urllib.request.Request(url, headers={"User-Agent": "subsetted-distribution-creation-action"})
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

