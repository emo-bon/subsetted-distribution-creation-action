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
