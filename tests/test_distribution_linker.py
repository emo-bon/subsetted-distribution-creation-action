from pathlib import Path
import rdflib
from action.distribution_linker import link_distribution_in_triples

INITIAL_TURTLE = """
@prefix schema: <https://schema.org/> .
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct: <http://purl.org/dc/terms/> .

<https://data.emobon.embrc.eu/observatory-bpns-crate> a schema:Dataset, dcat:Dataset ;
    dct:title "BPNS Observatory Dataset" .
"""

def test_link_distribution_in_triples(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ttl_file = workspace / "all-triples.ttl"
    ttl_file.write_text(INITIAL_TURTLE)

    download_url = "https://github.com/emo-bon/observatory-bpns-crate/releases/download/bluecloud-ENA-latest/BPNS_bluecloud-ENA.zip"
    link_distribution_in_triples(workspace, "emo-bon/observatory-bpns-crate", "BPNS", "bluecloud-ENA", download_url)

    g = rdflib.Graph()
    g.parse(ttl_file, format="turtle")

    dist_uri = rdflib.URIRef("https://data.emobon.embrc.eu/observatory-bpns-crate/distribution/bluecloud-ENA")
    assert (dist_uri, rdflib.RDF.type, rdflib.URIRef("http://www.w3.org/ns/dcat#Distribution")) in g
    assert (dist_uri, rdflib.RDF.type, rdflib.URIRef("https://schema.org/DataDownload")) in g
    assert (dist_uri, rdflib.URIRef("http://www.w3.org/ns/dcat#downloadURL"), rdflib.URIRef(download_url)) in g
    assert (dist_uri, rdflib.URIRef("https://schema.org/contentUrl"), rdflib.URIRef(download_url)) in g

    dataset_uri = rdflib.URIRef("https://data.emobon.embrc.eu/observatory-bpns-crate")
    assert (dataset_uri, rdflib.URIRef("http://www.w3.org/ns/dcat#distribution"), dist_uri) in g
    assert (dataset_uri, rdflib.URIRef("https://schema.org/distribution"), dist_uri) in g
