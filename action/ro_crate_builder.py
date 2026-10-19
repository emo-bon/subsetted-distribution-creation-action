import json
from pathlib import Path
from typing import Any, Dict
import yaml

try:
    from sema.ro.creator import ROCreator
    from sema.commons.yml.loader import LoaderBuilder
except ImportError:
    ROCreator = None
    LoaderBuilder = None

BLUEPRINT_FILE = Path(__file__).parent / "blueprints" / "bluecloud_ro_blueprint.yml"

def build_ro_crate(output_dir: Path, metadata: Dict[str, Any]) -> Path:
    """
    Constructs ro-crate-metadata.json in output_dir using pysema ROCreator.
    If pysema process encounters an issue, generates standard RO-Crate 1.2 compliant dictionary.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "ro-crate-metadata.json"

    def _escape_literal(val: Any) -> Any:
        if isinstance(val, str) and not val.startswith("http://") and not val.startswith("https://") and not val.startswith("_:") and not val.startswith("urn:"):
            if ":" in val:
                return val.replace(":", "\\:")
        return val

    blueprint_env = {
        "TITLE": _escape_literal(metadata["title"]),
        "DESCRIPTION": _escape_literal(metadata["description"]),
        "DATE_PUBLISHED": metadata["date_published"],
        "DATE_MODIFIED": metadata["date_modified"],
        "REPO_LANDING_URL": metadata["repo_landing_url"],
        "RELEASE_TAG_URL": metadata["release_tag_url"],
        "CITATION_TEXT": _escape_literal(metadata["citation_text"]),
        "TEMPORAL_COVERAGE": metadata["temporal_coverage"],
        "OBSERVATORY_NAME": _escape_literal(metadata["observatory_name"]),
        "COUNTRY": _escape_literal(metadata.get("country", "")),
        "GEO_BBOX": metadata["geo_bbox"],
    }


    # Dynamic Blueprint generation to include parameter and organization nodes
    if LoaderBuilder:
        loader = LoaderBuilder().to_resolve(blueprint_env).build()
        with open(BLUEPRINT_FILE, "r", encoding="utf-8") as f:
            blueprint_data = yaml.load(f, Loader=loader) or {}
    else:
        class BlueprintLoader(yaml.SafeLoader):
            pass

        def _resolve_tag_constructor(loader, node):
            if isinstance(node, yaml.ScalarNode):
                txt = loader.construct_scalar(node)
                try:
                    return txt.format(**blueprint_env)
                except Exception:
                    return txt
            elif isinstance(node, yaml.SequenceNode):
                return loader.construct_sequence(node)
            elif isinstance(node, yaml.MappingNode):
                return loader.construct_mapping(node)
            return None

        BlueprintLoader.add_constructor("!resolve", _resolve_tag_constructor)
        BlueprintLoader.add_constructor(None, _resolve_tag_constructor)

        with open(BLUEPRINT_FILE, "r", encoding="utf-8") as f:
            blueprint_data = yaml.load(f, Loader=BlueprintLoader) or {}

    # Ensure prefix definition for blank nodes
    blueprint_data.setdefault("$", {}).setdefault("prefix", {})["_"] = "_:"


    root_dataset = blueprint_data.setdefault("./", {})

    creator_uris = []
    for org in metadata.get("organizations", []):
        url = org.get("edmo_url") or f"urn:org:{org['name']}"
        creator_uris.append(url)
        blueprint_data[url] = {
            "$type": "Organization",
            "name": _escape_literal(org["name"]),
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
            "name": _escape_literal(param["name"]),
        }
        if param.get("property_id"):
            node["propertyID"] = param["property_id"]
        blueprint_data[bnode_id] = node
    if var_measured:
        root_dataset["variableMeasured"] = var_measured

    if metadata.get("instruments"):
        root_dataset["instrument"] = [_escape_literal(i) for i in metadata["instruments"]]


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

    built_with_creator = False
    if ROCreator:
        try:
            creator = ROCreator(
                blueprint_path=temp_blueprint,
                blueprint_env=blueprint_env,
                rocrate_path=output_dir,
                force=True,
            )
            creator.process()
            built_with_creator = destination.exists()
        except Exception as e:
            print(f"Warning: ROCreator process raised {e}, writing fallback JSON-LD directly.")

    if not built_with_creator:
        _write_fallback_ro_crate(destination, metadata, output_dir=output_dir)

    if temp_blueprint.exists():
        temp_blueprint.unlink()

    return destination

def _write_fallback_ro_crate(destination: Path, metadata: Dict[str, Any], output_dir: Path = None) -> None:
    root_dataset = {
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
    }

    if metadata.get("parameters"):
        root_dataset["variableMeasured"] = [{"@id": f"_:param_{idx}"} for idx in range(len(metadata["parameters"]))]

    if metadata.get("instruments"):
        root_dataset["instrument"] = metadata["instruments"]

    if output_dir:
        has_part = []
        for candidate in ("all-triples.ttl", "ena_accessions_subset.csv", "README.md"):
            if (output_dir / candidate).exists():
                has_part.append({"@id": candidate})
        if (output_dir / "logsheets").exists():
            has_part.append({"@id": "logsheets/"})
        if has_part:
            root_dataset["hasPart"] = has_part

    graph = [
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "conformsTo": {"@id": "https://w3id.org/ro/crate/1.2"},
            "about": {"@id": "./"},
        },
        root_dataset,

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
