"""
Tests for the NetworkBuilder service and Union-Find.
"""
import pytest

from src.api.services.network_builder import UnionFind, _sse_event, _edge_key


class TestUnionFind:
    """Tests for Union-Find data structure."""

    def test_find_creates_singleton(self):
        uf = UnionFind()
        assert uf.find("A") == "A"
        assert uf.component_count() == 1

    def test_union_merges_components(self):
        uf = UnionFind()
        uf.find("A")
        uf.find("B")
        assert uf.component_count() == 2

        merged = uf.union("A", "B")
        assert merged is True
        assert uf.component_count() == 1

    def test_union_same_component_returns_false(self):
        uf = UnionFind()
        uf.union("A", "B")
        merged = uf.union("A", "B")
        assert merged is False

    def test_connected(self):
        uf = UnionFind()
        uf.find("A")
        uf.find("B")
        uf.find("C")
        assert uf.connected("A", "B") is False

        uf.union("A", "B")
        assert uf.connected("A", "B") is True
        assert uf.connected("A", "C") is False

    def test_transitive_connectivity(self):
        uf = UnionFind()
        uf.union("A", "B")
        uf.union("B", "C")
        assert uf.connected("A", "C") is True
        assert uf.component_count() == 1

    def test_components(self):
        uf = UnionFind()
        uf.union("A", "B")
        uf.union("C", "D")
        components = uf.components()
        assert len(components) == 2
        # Check each component has the right members
        members = [sorted(v) for v in components.values()]
        assert sorted(members) == [["A", "B"], ["C", "D"]]

    def test_all_seeds_connected_single(self):
        uf = UnionFind()
        uf.find("A")
        assert uf.all_seeds_connected(["A"]) is True

    def test_all_seeds_connected_true(self):
        uf = UnionFind()
        uf.union("A", "B")
        uf.union("B", "C")
        assert uf.all_seeds_connected(["A", "B", "C"]) is True

    def test_all_seeds_connected_false(self):
        uf = UnionFind()
        uf.union("A", "B")
        uf.find("C")
        assert uf.all_seeds_connected(["A", "B", "C"]) is False

    def test_many_elements(self):
        uf = UnionFind()
        # Create a chain: 0-1-2-...-99
        ids = [f"A{i}" for i in range(100)]
        for i in range(99):
            uf.union(ids[i], ids[i + 1])
        assert uf.component_count() == 1
        assert uf.connected(ids[0], ids[99]) is True

    def test_path_compression(self):
        """After find, parent should point closer to root."""
        uf = UnionFind()
        # Build a chain
        uf.union("A", "B")
        uf.union("B", "C")
        uf.union("C", "D")
        # Find D — should compress path
        root = uf.find("D")
        # After compression, D's parent should be closer to root
        assert uf.find("D") == root
        assert uf.find("C") == root


class TestSSEHelpers:
    """Tests for SSE formatting helpers."""

    def test_sse_event_format(self):
        result = _sse_event("node", {"id": "A123", "label": "Test"})
        assert result.startswith("event: node\n")
        assert "data: " in result
        assert result.endswith("\n\n")
        assert '"id": "A123"' in result

    def test_sse_event_unicode(self):
        result = _sse_event("node", {"label": "张三"})
        assert "张三" in result  # ensure_ascii=False

    def test_edge_key_ordering(self):
        assert _edge_key("B", "A") == ("A", "B")
        assert _edge_key("A", "B") == ("A", "B")
        assert _edge_key("A", "A") == ("A", "A")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
