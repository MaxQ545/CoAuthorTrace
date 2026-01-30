"""GNN models for relationship analysis."""
from .graphsage import GraphSAGEModel, train_graphsage, get_embeddings

__all__ = ["GraphSAGEModel", "train_graphsage", "get_embeddings"]
