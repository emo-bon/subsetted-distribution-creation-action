from pathlib import Path
from typing import Set
import rdflib
from rdflib import BNode, Graph, URIRef
from rdflib.namespace import RDF

SOSA_IS_RESULT_OF = URIRef("http://www.w3.org/ns/sosa/isResultOf")
SOSA_HAS_FOI = URIRef("http://www.w3.org/ns/sosa/hasFeatureOfInterest")
EMOBON_OBSERVATORY = URIRef("https://data.emobon.embrc.eu/ns/core#Observatory")

def subset_rdf_graph(
    workspace_dir: Path,
    output_dir: Path,
    qualifying_events: Set[str]
) -> Path:
    """
    Subsets all-triples.ttl into output_dir/all-triples.ttl containing only the subgraphs
    for qualifying_events, their samples, observations, blank nodes, and observatory info.
    """
    src_ttl = workspace_dir / "all-triples.ttl"
    out_ttl = output_dir / "all-triples.ttl"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not src_ttl.exists():
        Graph().serialize(out_ttl, format="turtle")
        return out_ttl

    src_graph = Graph()
    src_graph.parse(src_ttl, format="turtle")

    sub_graph = Graph()
    # Copy namespaces
    for prefix, ns in src_graph.namespaces():
        sub_graph.bind(prefix, ns)

    # 1. Find target event URIs
    target_event_uris: Set[URIRef] = set()
    for s in src_graph.subjects():
        if isinstance(s, URIRef):
            s_str = str(s)
            for ev in qualifying_events:
                if s_str.endswith(f"/sampling-event/{ev}") or s_str.endswith(f"/{ev}"):
                    target_event_uris.add(s)

    nodes_to_traverse: Set[rdflib.term.Identifier] = set(target_event_uris)

    # 2. Find samples linked to target events: ?sample sosa:isResultOf ?event
    sample_uris: Set[URIRef] = set()
    for ev_uri in target_event_uris:
        for sample in src_graph.subjects(SOSA_IS_RESULT_OF, ev_uri):
            sample_uris.add(sample)
            nodes_to_traverse.add(sample)

    # 3. Find observations linked to samples: ?obs sosa:hasFeatureOfInterest ?sample
    for sample in sample_uris:
        for obs in src_graph.subjects(SOSA_HAS_FOI, sample):
            nodes_to_traverse.add(obs)

    # 4. Find observatory entity: ?obs a emobon-core:Observatory
    for obs_entity in src_graph.subjects(RDF.type, EMOBON_OBSERVATORY):
        nodes_to_traverse.add(obs_entity)

    # 5. Extract all outgoing triples and recursively extract blank nodes
    visited: Set[rdflib.term.Identifier] = set()
    queue = list(nodes_to_traverse)

    while queue:
        node = queue.pop()
        if node in visited:
            continue
        visited.add(node)

        for p, o in src_graph.predicate_objects(node):
            sub_graph.add((node, p, o))
            if isinstance(o, BNode) and o not in visited:
                queue.append(o)

    sub_graph.serialize(out_ttl, format="turtle")
    return out_ttl
