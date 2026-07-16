from specir.core import Edge, Entity, Section, SpecIRGraph


def test_graph_round_trip(tmp_path):
    graph = SpecIRGraph()
    graph.add_node(Section("demo:1", "demo", "1", "Overview", text="Hello"))
    graph.add_node(Entity("demo:command:a1", "demo", "command", "A1", "Read"))
    graph.add_edge(Edge("demo:1", "demo:command:a1", "defines"))
    graph.save(tmp_path)
    loaded = SpecIRGraph.load(tmp_path)
    assert loaded.get_node("demo:1")["title"] == "Overview"
    assert loaded.get_edges_from("demo:1")[0]["type"] == "defines"
