"""
Relationship scorer combining GraphSAGE embeddings and weighted metrics.
"""
import logging
from datetime import datetime
from typing import Optional

import numpy as np
import torch
import networkx as nx
from sqlalchemy.orm import Session

from config.settings import settings
from src.database.models import Author, Collaboration, RelationshipScore, get_session
from src.database.repositories import CollaborationRepository
from src.analysis.graph_builder import GraphBuilder
from src.analysis.models.graphsage import (
    GraphSAGEModel,
    train_graphsage,
    get_embeddings,
    save_model,
    load_model,
)

logger = logging.getLogger(__name__)


class RelationshipScorer:
    """
    Computes and stores relationship scores between authors.

    Combines:
    1. GraphSAGE embedding similarity
    2. Weighted collaboration scores
    3. Network centrality metrics
    """

    def __init__(
        self,
        session: Optional[Session] = None,
        model_path: Optional[str] = None,
    ):
        """
        Initialize relationship scorer.

        Args:
            session: Database session
            model_path: Path to trained GraphSAGE model
        """
        self.session = session or get_session()
        self.model_path = model_path
        self.graph_builder = GraphBuilder(self.session)
        self.model: Optional[GraphSAGEModel] = None
        self.embeddings: Optional[torch.Tensor] = None
        self.graph_data = None
        self._nx_graph: Optional[nx.Graph] = None

    def train_model(
        self,
        min_collaborations: int = 1,
        hidden_dim: Optional[int] = None,
        output_dim: Optional[int] = None,
        num_layers: Optional[int] = None,
        epochs: Optional[int] = None,
        learning_rate: Optional[float] = None,
    ) -> dict:
        """
        Train GraphSAGE model on collaboration graph.

        Args:
            min_collaborations: Minimum collaborations for edge inclusion
            hidden_dim: Hidden dimension (default: from settings)
            output_dim: Output dimension (default: from settings)
            num_layers: Number of layers (default: from settings)
            epochs: Training epochs (default: from settings)
            learning_rate: Learning rate (default: from settings)

        Returns:
            Training statistics
        """
        # Use settings defaults
        hidden_dim = hidden_dim or settings.analysis.hidden_dim
        output_dim = output_dim or settings.analysis.output_dim
        num_layers = num_layers or settings.analysis.num_layers
        epochs = epochs or settings.analysis.epochs
        learning_rate = learning_rate or settings.analysis.learning_rate

        # Build graph
        logger.info("Building collaboration graph...")
        self.graph_data = self.graph_builder.build_graph(
            min_collaborations=min_collaborations
        )

        if self.graph_data.edge_index.size(1) == 0:
            logger.warning("No edges in graph, skipping training")
            return {"status": "skipped", "reason": "no_edges"}

        # Train model
        logger.info("Training GraphSAGE model...")
        self.model, losses = train_graphsage(
            self.graph_data,
            hidden_dim=hidden_dim,
            output_dim=output_dim,
            num_layers=num_layers,
            epochs=epochs,
            learning_rate=learning_rate,
        )

        # Get embeddings
        self.embeddings = get_embeddings(self.model, self.graph_data)

        # Save model
        if self.model_path:
            save_model(
                self.model,
                self.model_path,
                metadata={
                    "trained_at": datetime.utcnow().isoformat(),
                    "num_nodes": self.graph_data.num_nodes,
                    "num_edges": self.graph_data.edge_index.size(1) // 2,
                }
            )

        return {
            "status": "completed",
            "num_nodes": self.graph_data.num_nodes,
            "num_edges": self.graph_data.edge_index.size(1) // 2,
            "final_loss": losses[-1] if losses else None,
        }

    def load_model(self, path: Optional[str] = None):
        """Load trained model from disk."""
        path = path or self.model_path
        if path:
            self.model = load_model(path)

    def compute_graphsage_similarity(
        self,
        author_id_1: str,
        author_id_2: str,
    ) -> Optional[float]:
        """
        Compute cosine similarity between author embeddings.

        Args:
            author_id_1: First author ID
            author_id_2: Second author ID

        Returns:
            Similarity score (0-1) or None if not available
        """
        if self.embeddings is None or self.graph_data is None:
            return None

        idx_1 = self.graph_data.author_id_to_idx.get(author_id_1)
        idx_2 = self.graph_data.author_id_to_idx.get(author_id_2)

        if idx_1 is None or idx_2 is None:
            return None

        emb_1 = self.embeddings[idx_1]
        emb_2 = self.embeddings[idx_2]

        # Cosine similarity (embeddings are already normalized)
        similarity = torch.dot(emb_1, emb_2).item()

        # Scale to 0-1 range
        return (similarity + 1) / 2

    def compute_weighted_score(
        self,
        author_id_1: str,
        author_id_2: str,
    ) -> Optional[float]:
        """
        Get weighted collaboration score.

        Args:
            author_id_1: First author ID
            author_id_2: Second author ID

        Returns:
            Weighted score or None
        """
        collab_repo = CollaborationRepository(self.session)
        collab = collab_repo.get_collaboration(author_id_1, author_id_2)

        if collab is None:
            return None

        return collab.total_weight

    def compute_combined_score(
        self,
        author_id_1: str,
        author_id_2: str,
        graphsage_weight: float = 0.5,
        weighted_weight: float = 0.5,
    ) -> Optional[float]:
        """
        Compute combined relationship score.

        Args:
            author_id_1: First author ID
            author_id_2: Second author ID
            graphsage_weight: Weight for GraphSAGE similarity
            weighted_weight: Weight for collaboration weight

        Returns:
            Combined score or None
        """
        graphsage_sim = self.compute_graphsage_similarity(author_id_1, author_id_2)
        weighted = self.compute_weighted_score(author_id_1, author_id_2)

        if graphsage_sim is None and weighted is None:
            return None

        # Normalize weighted score (log scale)
        if weighted is not None and weighted > 0:
            weighted_normalized = np.log1p(weighted) / 10  # Normalize to ~0-1 range
            weighted_normalized = min(weighted_normalized, 1.0)
        else:
            weighted_normalized = 0.0

        # Combine scores
        if graphsage_sim is not None and weighted is not None:
            return graphsage_weight * graphsage_sim + weighted_weight * weighted_normalized
        elif graphsage_sim is not None:
            return graphsage_sim
        else:
            return weighted_normalized

    def compute_all_scores(
        self,
        batch_size: int = 1000,
        model_version: Optional[str] = None,
    ) -> int:
        """
        Compute and store relationship scores for all collaborations.

        Args:
            batch_size: Number of scores to compute before committing
            model_version: Version string for tracking

        Returns:
            Number of scores computed
        """
        logger.info("Computing relationship scores...")

        # Get all collaborations
        collaborations = self.session.query(Collaboration).all()
        logger.info(f"Processing {len(collaborations)} collaborations")

        collab_repo = CollaborationRepository(self.session)
        count = 0

        for i, collab in enumerate(collaborations):
            graphsage_score = self.compute_graphsage_similarity(
                collab.author_id_1,
                collab.author_id_2,
            )
            weighted_score = collab.total_weight
            combined_score = self.compute_combined_score(
                collab.author_id_1,
                collab.author_id_2,
            )

            collab_repo.save_relationship_score(
                author_id_1=collab.author_id_1,
                author_id_2=collab.author_id_2,
                graphsage_score=graphsage_score,
                weighted_score=weighted_score,
                combined_score=combined_score,
                model_version=model_version,
            )
            count += 1

            if (i + 1) % batch_size == 0:
                self.session.commit()
                logger.info(f"Processed {i + 1}/{len(collaborations)} scores")

        self.session.commit()
        logger.info(f"Computed {count} relationship scores")

        return count

    def get_top_relations(
        self,
        author_id: str,
        k: int = 20,
        score_type: str = "combined_score",
    ) -> list[tuple[str, str, float]]:
        """
        Get top-K related authors for a given author.

        Args:
            author_id: Author ID to query
            k: Number of relations to return
            score_type: Score type to sort by

        Returns:
            List of (author_id, display_name, score) tuples
        """
        from sqlalchemy import or_

        score_col = getattr(RelationshipScore, score_type)

        # Use JOIN to avoid N+1 queries
        # Query where author is author_1
        q1 = (
            self.session.query(Author.id, Author.display_name, score_col)
            .join(RelationshipScore, Author.id == RelationshipScore.author_id_2)
            .filter(RelationshipScore.author_id_1 == author_id)
            .filter(score_col.isnot(None))
        )

        # Query where author is author_2
        q2 = (
            self.session.query(Author.id, Author.display_name, score_col)
            .join(RelationshipScore, Author.id == RelationshipScore.author_id_1)
            .filter(RelationshipScore.author_id_2 == author_id)
            .filter(score_col.isnot(None))
        )

        # Union and order
        results = (
            q1.union(q2)
            .order_by(score_col.desc())
            .limit(k)
            .all()
        )

        return [(aid, name, score) for aid, name, score in results]

    # NetworkX centrality metrics
    # Cache for precomputed metrics (populated by run_analysis)
    _centrality_cache = {}

    def _build_nx_graph(self, max_nodes: int = 50000) -> nx.Graph:
        """Build NetworkX graph from collaborations."""
        if self._nx_graph is not None:
            return self._nx_graph

        G = nx.Graph()

        # Add nodes (with limit to prevent OOM)
        authors = self.session.query(Author).limit(max_nodes).all()
        author_ids = set()
        for author in authors:
            G.add_node(author.id, name=author.display_name)
            author_ids.add(author.id)

        # Add edges (only for nodes we have)
        collaborations = self.session.query(Collaboration).filter(
            Collaboration.author_id_1.in_(author_ids),
            Collaboration.author_id_2.in_(author_ids),
        ).all()
        for collab in collaborations:
            G.add_edge(
                collab.author_id_1,
                collab.author_id_2,
                weight=collab.total_weight,
                count=collab.collaboration_count,
            )

        self._nx_graph = G
        return G

    def _build_ego_graph(self, author_id: str, radius: int = 2, max_neighbors: int = 500) -> nx.Graph:
        """Build a local ego graph centered on an author (much faster than full graph)."""
        from sqlalchemy import or_

        G = nx.Graph()
        visited = set()
        to_visit = {author_id}
        depth = 0

        while to_visit and depth <= radius and len(visited) < max_neighbors:
            current_level = to_visit
            to_visit = set()

            for aid in current_level:
                if aid in visited:
                    continue
                visited.add(aid)

                # Get author info
                author = self.session.query(Author).filter(Author.id == aid).first()
                if author:
                    G.add_node(aid, name=author.display_name)

                # Get collaborations (limited)
                collabs = (
                    self.session.query(Collaboration)
                    .filter(or_(
                        Collaboration.author_id_1 == aid,
                        Collaboration.author_id_2 == aid,
                    ))
                    .limit(100)  # Limit per node
                    .all()
                )

                for collab in collabs:
                    other_id = collab.author_id_2 if collab.author_id_1 == aid else collab.author_id_1
                    if other_id not in visited and depth < radius:
                        to_visit.add(other_id)
                    if aid in G and other_id in G:
                        G.add_edge(aid, other_id, weight=collab.total_weight)
                    elif aid in G:
                        # Add the other node too
                        other = self.session.query(Author).filter(Author.id == other_id).first()
                        if other:
                            G.add_node(other_id, name=other.display_name)
                            G.add_edge(aid, other_id, weight=collab.total_weight)

            depth += 1

        return G

    def _build_institution_graph(self, institution_id: str, max_nodes: int = 5000) -> nx.Graph:
        """Build a graph of authors within the same institution."""
        from sqlalchemy import and_

        G = nx.Graph()

        # Get all canonical authors in this institution
        authors = (
            self.session.query(Author)
            .filter(
                Author.last_known_institution_id == institution_id,
                Author.is_canonical == True
            )
            .limit(max_nodes)
            .all()
        )

        author_ids = set()
        for author in authors:
            G.add_node(author.id, name=author.display_name)
            author_ids.add(author.id)

        if len(author_ids) < 2:
            return G

        # Get collaborations between these authors
        collaborations = (
            self.session.query(Collaboration)
            .filter(
                Collaboration.author_id_1.in_(author_ids),
                Collaboration.author_id_2.in_(author_ids)
            )
            .all()
        )

        for collab in collaborations:
            G.add_edge(
                collab.author_id_1,
                collab.author_id_2,
                weight=collab.total_weight,
                count=collab.collaboration_count,
            )

        return G

    def compute_centrality_metrics(
        self,
        author_id: str,
    ) -> dict:
        """
        Compute network centrality metrics for an author within their institution.

        Uses institution-scoped graph for meaningful comparison with colleagues.

        Args:
            author_id: Author ID

        Returns:
            Dictionary of centrality metrics including institution info
        """
        # Check if we have precomputed metrics
        if author_id in self._centrality_cache:
            return self._centrality_cache[author_id]

        # Get author's institution
        author = self.session.query(Author).filter(Author.id == author_id).first()
        if not author:
            return {}

        institution_id = author.last_known_institution_id
        institution_name = author.last_known_institution_name

        # Build institution graph if author has an institution
        if institution_id:
            G = self._build_institution_graph(institution_id, max_nodes=5000)
        else:
            # Fallback to ego graph if no institution
            G = self._build_ego_graph(author_id, radius=2, max_neighbors=500)

        if author_id not in G or G.number_of_nodes() < 2:
            return {"institution_name": institution_name, "institution_author_count": 0}

        metrics = {
            "institution_name": institution_name,
            "institution_author_count": G.number_of_nodes(),
        }

        try:
            # Degree centrality (fast)
            degree_cent = nx.degree_centrality(G)
            metrics["degree_centrality"] = degree_cent.get(author_id, 0)

            # Local clustering coefficient (fast)
            metrics["clustering_coefficient"] = nx.clustering(G, author_id, weight="weight")

            # PageRank (works on any graph size)
            try:
                pagerank = nx.pagerank(G, weight="weight", max_iter=100)
                metrics["pagerank"] = pagerank.get(author_id, 0)
            except Exception as e:
                logger.warning(f"PageRank failed for {author_id}: {e}")

            # Betweenness centrality (use sampling for large graphs)
            try:
                k = min(100, G.number_of_nodes())  # Sample size
                betweenness = nx.betweenness_centrality(G, k=k, weight="weight")
                metrics["betweenness_centrality"] = betweenness.get(author_id, 0)
            except Exception as e:
                logger.debug(f"Betweenness failed: {e}")

            # Closeness centrality (compute for single source node - much faster)
            try:
                if author_id in G:
                    path_lengths = nx.single_source_shortest_path_length(G, author_id)
                    if len(path_lengths) > 1:
                        total_distance = sum(path_lengths.values())
                        metrics["closeness_centrality"] = (len(path_lengths) - 1) / total_distance if total_distance > 0 else 0
            except Exception as e:
                logger.debug(f"Closeness failed: {e}")

            # Eigenvector centrality (can fail on disconnected graphs)
            try:
                eigenvector = nx.eigenvector_centrality(G, weight="weight", max_iter=100)
                metrics["eigenvector_centrality"] = eigenvector.get(author_id, 0)
            except Exception as e:
                logger.debug(f"Eigenvector failed: {e}")

        except Exception as e:
            logger.warning(f"Error computing centrality for {author_id}: {e}")

        return metrics


def run_analysis(
    model_path: Optional[str] = None,
    min_collaborations: int = 1,
) -> dict:
    """
    Run full analysis pipeline.

    Args:
        model_path: Path to save/load model
        min_collaborations: Minimum collaborations for inclusion

    Returns:
        Analysis statistics
    """
    scorer = RelationshipScorer(model_path=model_path)

    # Train model
    train_stats = scorer.train_model(min_collaborations=min_collaborations)

    if train_stats["status"] != "completed":
        return train_stats

    # Compute all scores
    model_version = f"v{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    num_scores = scorer.compute_all_scores(model_version=model_version)

    return {
        "status": "completed",
        "train_stats": train_stats,
        "num_scores": num_scores,
        "model_version": model_version,
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    from src.database.models import init_database
    init_database()

    model_path = sys.argv[1] if len(sys.argv) > 1 else "data/models/graphsage.pt"
    stats = run_analysis(model_path=model_path)
    print(f"Analysis completed: {stats}")
