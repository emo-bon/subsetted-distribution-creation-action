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
