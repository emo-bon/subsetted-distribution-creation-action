from pathlib import Path
import rdflib
from action.graph_subsetter import subset_rdf_graph

SAMPLE_TURTLE = """
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix emobon-core: <https://data.emobon.embrc.eu/ns/core#> .
@prefix qudt: <http://qudt.org/schema/qudt/> .

<http://example.org/event/BPNS_So_210726> a sosa:Sampling, prov:Activity ;
    sosa:resultTime "2021-07-26" .

<http://example.org/sample/EMOBON_BPNS_So_5> a sosa:Sample ;
    sosa:isResultOf <http://example.org/event/BPNS_So_210726> .

<http://example.org/obs/1> a sosa:Observation ;
    sosa:hasFeatureOfInterest <http://example.org/sample/EMOBON_BPNS_So_5> ;
    sosa:hasResult [ a qudt:QuantityValue ; qudt:numericValue 7.5 ] .

# Unrelated event
<http://example.org/event/BPNS_So_999999> a sosa:Sampling ;
    sosa:resultTime "2099-01-01" .
<http://example.org/sample/EMOBON_BPNS_So_99> a sosa:Sample ;
    sosa:isResultOf <http://example.org/event/BPNS_So_999999> .

<http://example.org/observatory/BPNS> a emobon-core:Observatory ;
    emobon-core:observatoryId "BPNS" .
"""

def test_subset_rdf_graph(tmp_path: Path):
    workspace = tmp_path / "workspace"
    out_dir = tmp_path / "output"
    workspace.mkdir()
    ttl_file = workspace / "all-triples.ttl"
    ttl_file.write_text(SAMPLE_TURTLE)

    out_ttl = subset_rdf_graph(workspace, out_dir, {"BPNS_So_210726"})

    assert out_ttl.exists()
    g = rdflib.Graph()
    g.parse(out_ttl, format="turtle")

    # Target event and its samples/observations should exist
    assert (rdflib.URIRef("http://example.org/event/BPNS_So_210726"), None, None) in g
    assert (rdflib.URIRef("http://example.org/sample/EMOBON_BPNS_So_5"), None, None) in g
    assert (rdflib.URIRef("http://example.org/obs/1"), None, None) in g

    # Observatory entity should exist
    assert (rdflib.URIRef("http://example.org/observatory/BPNS"), None, None) in g

    # Unrelated event and sample must NOT exist
    assert (rdflib.URIRef("http://example.org/event/BPNS_So_999999"), None, None) not in g
    assert (rdflib.URIRef("http://example.org/sample/EMOBON_BPNS_So_99"), None, None) not in g
