"""
Graph builder for constructing PyTorch Geometric graphs from database.
"""
import logging
from typing import Optional
import math

import numpy as np
import torch
from torch_geometric.data import Data
from sqlalchemy.orm import Session

from src.database.models import Author, Collaboration, get_session

logger = logging.getLogger(__name__)


class GraphBuilder:
    """
    Builds PyTorch Geometric graph from collaboration data.
    """

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize graph builder.

        Args:
            session: Database session (creates new if not provided)
        """
        self.session = session or get_session()
        self._author_id_to_idx: dict[str, int] = {}
        self._idx_to_author_id: dict[int, str] = {}
        self._cached_graph: Optional[Data] = None
        self._cache_params: Optional[tuple] = None

    def invalidate_cache(self):
        """Invalidate the cached graph, forcing a rebuild on next access."""
        self._cached_graph = None
        self._cache_params = None

    def build_graph(
        self,
        min_collaborations: int = 1,
        min_weight: float = 0.0,
    ) -> Data:
        """
        Build PyTorch Geometric graph from database.

        Uses instance-level caching to avoid rebuilding when called with the
        same parameters. Call invalidate_cache() when underlying data changes.

        Args:
            min_collaborations: Minimum collaboration count for edge inclusion
            min_weight: Minimum weight for edge inclusion

        Returns:
            PyTorch Geometric Data object
        """
        cache_key = (min_collaborations, min_weight)
        if self._cached_graph is not None and self._cache_params == cache_key:
            logger.debug("Returning cached graph")
            return self._cached_graph

        logger.info("Building collaboration graph...")

        # Get all authors with at least one collaboration
        authors = self._get_active_authors(min_collaborations)
        logger.info(f"Found {len(authors)} active authors")

        # Build author index mapping
        self._author_id_to_idx = {a.id: idx for idx, a in enumerate(authors)}
        self._idx_to_author_id = {idx: a.id for idx, a in enumerate(authors)}

        # Build node features
        node_features = self._build_node_features(authors)
        logger.info(f"Built node features: shape {node_features.shape}")

        # Build edge index and weights
        edge_index, edge_weight = self._build_edges(min_collaborations, min_weight)
        logger.info(f"Built edges: {edge_index.shape[1]} edges")

        # Create PyTorch Geometric Data object
        data = Data(
            x=node_features,
            edge_index=edge_index,
            edge_attr=edge_weight,
        )

        # Store mappings as data attributes
        data.author_id_to_idx = self._author_id_to_idx
        data.idx_to_author_id = self._idx_to_author_id

        # Cache the built graph
        self._cached_graph = data
        self._cache_params = (min_collaborations, min_weight)

        return data

    def _get_active_authors(self, min_collaborations: int) -> list[Author]:
        """Get authors with at least the minimum number of collaborations."""
        from sqlalchemy import or_, func

        # Get author IDs that appear in collaborations
        collab_authors = (
            self.session.query(Collaboration.author_id_1)
            .union(self.session.query(Collaboration.author_id_2))
            .subquery()
        )

        authors = (
            self.session.query(Author)
            .filter(Author.id.in_(self.session.query(collab_authors)))
            .all()
        )

        return authors

    def _build_node_features(self, authors: list[Author]) -> torch.Tensor:
        """
        Build node feature matrix.

        Features:
        - log(works_count + 1) (normalized)
        - log(cited_by_count + 1) (normalized)
        - collaboration count (will be computed)
        - has_orcid (binary)
        """
        features = []

        # Get collaboration counts
        collab_counts = self._get_collaboration_counts()

        for author in authors:
            # Log-normalize counts
            works = math.log1p(author.works_count or 0)
            citations = math.log1p(author.cited_by_count or 0)
            collabs = math.log1p(collab_counts.get(author.id, 0))
            has_orcid = 1.0 if author.orcid else 0.0

            features.append([works, citations, collabs, has_orcid])

        feature_tensor = torch.tensor(features, dtype=torch.float)

        # Normalize features (z-score normalization)
        mean = feature_tensor.mean(dim=0, keepdim=True)
        std = feature_tensor.std(dim=0, keepdim=True)
        std[std == 0] = 1  # Avoid division by zero

        normalized = (feature_tensor - mean) / std

        return normalized

    def _get_collaboration_counts(self) -> dict[str, int]:
        """Get collaboration count for each author."""
        from sqlalchemy import func, or_

        # Count collaborations for author_id_1
        counts_1 = (
            self.session.query(
                Collaboration.author_id_1,
                func.sum(Collaboration.collaboration_count)
            )
            .group_by(Collaboration.author_id_1)
            .all()
        )

        # Count collaborations for author_id_2
        counts_2 = (
            self.session.query(
                Collaboration.author_id_2,
                func.sum(Collaboration.collaboration_count)
            )
            .group_by(Collaboration.author_id_2)
            .all()
        )

        counts = {}
        for author_id, count in counts_1:
            counts[author_id] = counts.get(author_id, 0) + (count or 0)
        for author_id, count in counts_2:
            counts[author_id] = counts.get(author_id, 0) + (count or 0)

        return counts

    def _build_edges(
        self,
        min_collaborations: int,
        min_weight: float,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Build edge index and edge weights.

        Returns:
            Tuple of (edge_index, edge_weight) tensors
        """
        collaborations = (
            self.session.query(Collaboration)
            .filter(Collaboration.collaboration_count >= min_collaborations)
            .filter(Collaboration.total_weight >= min_weight)
            .all()
        )

        edge_list = []
        weights = []

        for collab in collaborations:
            # Get node indices
            idx_1 = self._author_id_to_idx.get(collab.author_id_1)
            idx_2 = self._author_id_to_idx.get(collab.author_id_2)

            if idx_1 is None or idx_2 is None:
                continue

            # Add edges in both directions (undirected graph)
            edge_list.append([idx_1, idx_2])
            edge_list.append([idx_2, idx_1])
            weights.append(collab.total_weight)
            weights.append(collab.total_weight)

        if not edge_list:
            # Return empty tensors if no edges
            return (
                torch.zeros((2, 0), dtype=torch.long),
                torch.zeros((0,), dtype=torch.float),
            )

        edge_index = torch.tensor(edge_list, dtype=torch.long).t().contiguous()
        edge_weight = torch.tensor(weights, dtype=torch.float)

        return edge_index, edge_weight

    def get_author_id(self, idx: int) -> Optional[str]:
        """Get author ID from node index."""
        return self._idx_to_author_id.get(idx)

    def get_author_idx(self, author_id: str) -> Optional[int]:
        """Get node index from author ID."""
        return self._author_id_to_idx.get(author_id)

    def get_subgraph(
        self,
        center_author_id: str,
        hops: int = 2,
    ) -> Optional[Data]:
        """
        Extract k-hop subgraph around a central author.

        Args:
            center_author_id: Author ID to center on
            hops: Number of hops to include

        Returns:
            Subgraph Data object or None if author not found
        """
        from torch_geometric.utils import k_hop_subgraph

        center_idx = self._author_id_to_idx.get(center_author_id)
        if center_idx is None:
            return None

        # Build full graph first
        full_graph = self.build_graph()

        # Extract subgraph
        subset, edge_index, mapping, edge_mask = k_hop_subgraph(
            node_idx=center_idx,
            num_hops=hops,
            edge_index=full_graph.edge_index,
            relabel_nodes=True,
        )

        # Create subgraph
        subgraph = Data(
            x=full_graph.x[subset],
            edge_index=edge_index,
            edge_attr=full_graph.edge_attr[edge_mask] if full_graph.edge_attr is not None else None,
        )

        # Map indices
        subgraph.original_indices = subset
        subgraph.center_idx = mapping

        return subgraph
