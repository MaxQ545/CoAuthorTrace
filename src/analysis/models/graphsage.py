"""
GraphSAGE model for learning author embeddings.

GraphSAGE learns node embeddings through neighborhood aggregation,
supporting inductive learning for new nodes.
"""
import logging
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv
from torch_geometric.data import Data

from config.settings import settings

logger = logging.getLogger(__name__)


class GraphSAGEModel(nn.Module):
    """
    GraphSAGE model for learning node embeddings.

    Architecture:
    - Multiple SAGEConv layers with ReLU activation
    - Dropout for regularization
    - Final layer produces embeddings
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 64,
        output_dim: int = 32,
        num_layers: int = 2,
        dropout: float = 0.5,
    ):
        """
        Initialize GraphSAGE model.

        Args:
            input_dim: Dimension of input node features
            hidden_dim: Dimension of hidden layers
            output_dim: Dimension of output embeddings
            num_layers: Number of SAGE convolution layers
            dropout: Dropout probability
        """
        super().__init__()

        self.num_layers = num_layers
        self.dropout = dropout

        # Build SAGE layers
        self.convs = nn.ModuleList()

        # First layer: input_dim -> hidden_dim
        self.convs.append(SAGEConv(input_dim, hidden_dim))

        # Middle layers: hidden_dim -> hidden_dim
        for _ in range(num_layers - 2):
            self.convs.append(SAGEConv(hidden_dim, hidden_dim))

        # Last layer: hidden_dim -> output_dim
        if num_layers > 1:
            self.convs.append(SAGEConv(hidden_dim, output_dim))
        else:
            # Single layer case
            self.convs[0] = SAGEConv(input_dim, output_dim)

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
    ) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Node feature matrix [num_nodes, input_dim]
            edge_index: Edge index [2, num_edges]

        Returns:
            Node embeddings [num_nodes, output_dim]
        """
        for i, conv in enumerate(self.convs):
            x = conv(x, edge_index)

            # Apply ReLU and dropout for all but last layer
            if i < len(self.convs) - 1:
                x = F.relu(x)
                x = F.dropout(x, p=self.dropout, training=self.training)

        # L2 normalize embeddings
        x = F.normalize(x, p=2, dim=-1)

        return x

    def get_embedding(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        node_idx: int,
    ) -> torch.Tensor:
        """
        Get embedding for a specific node.

        Args:
            x: Node feature matrix
            edge_index: Edge index
            node_idx: Index of the node

        Returns:
            Embedding vector [output_dim]
        """
        self.eval()
        with torch.no_grad():
            embeddings = self.forward(x, edge_index)
            return embeddings[node_idx]


class UnsupervisedLoss(nn.Module):
    """
    Unsupervised loss for GraphSAGE training.

    Uses negative sampling: maximize similarity between connected nodes,
    minimize similarity between random node pairs.
    """

    def __init__(self, num_negative_samples: int = 5):
        """
        Initialize loss function.

        Args:
            num_negative_samples: Number of negative samples per positive edge
        """
        super().__init__()
        self.num_negative_samples = num_negative_samples

    def forward(
        self,
        embeddings: torch.Tensor,
        edge_index: torch.Tensor,
        edge_weight: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute unsupervised loss.

        Args:
            embeddings: Node embeddings [num_nodes, dim]
            edge_index: Edge index [2, num_edges]
            edge_weight: Optional edge weights [num_edges]

        Returns:
            Loss value
        """
        num_nodes = embeddings.size(0)
        num_edges = edge_index.size(1)

        if num_edges == 0:
            return torch.tensor(0.0)

        # Positive samples: connected node pairs
        src = edge_index[0]
        dst = edge_index[1]

        # Compute positive pair similarities
        pos_sim = (embeddings[src] * embeddings[dst]).sum(dim=-1)

        if edge_weight is not None:
            pos_loss = -(edge_weight * F.logsigmoid(pos_sim)).mean()
        else:
            pos_loss = -F.logsigmoid(pos_sim).mean()

        # Negative samples: random node pairs (use randint for both to avoid memory explosion)
        num_neg = num_edges * self.num_negative_samples
        neg_src = torch.randint(0, num_nodes, (num_neg,), device=embeddings.device)
        neg_dst = torch.randint(0, num_nodes, (num_neg,), device=embeddings.device)

        neg_sim = (embeddings[neg_src] * embeddings[neg_dst]).sum(dim=-1)
        neg_loss = -F.logsigmoid(-neg_sim).mean()

        return pos_loss + neg_loss


def train_graphsage(
    data: Data,
    hidden_dim: int = 64,
    output_dim: int = 32,
    num_layers: int = 2,
    epochs: int = 100,
    learning_rate: float = 0.01,
    device: Optional[str] = None,
    early_stopping_patience: int = 10,
) -> tuple[GraphSAGEModel, list[float]]:
    """
    Train GraphSAGE model on graph data.

    Args:
        data: PyTorch Geometric Data object
        hidden_dim: Hidden layer dimension
        output_dim: Output embedding dimension
        num_layers: Number of SAGE layers
        epochs: Number of training epochs
        learning_rate: Learning rate
        device: Device to use (default: auto-detect)
        early_stopping_patience: Stop if loss doesn't improve for this many epochs (0 to disable)

    Returns:
        Tuple of (trained model, loss history)
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    logger.info(f"Training GraphSAGE on {device}")

    # Move data to device
    data = data.to(device)

    # Initialize model
    input_dim = data.x.size(1)
    model = GraphSAGEModel(
        input_dim=input_dim,
        hidden_dim=hidden_dim,
        output_dim=output_dim,
        num_layers=num_layers,
    ).to(device)

    # Initialize loss and optimizer
    criterion = UnsupervisedLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    # Training loop with early stopping
    losses = []
    model.train()
    best_loss = float("inf")
    best_state_dict = None
    patience_counter = 0

    for epoch in range(epochs):
        optimizer.zero_grad()

        embeddings = model(data.x, data.edge_index)
        loss = criterion(embeddings, data.edge_index, data.edge_attr)

        loss.backward()
        optimizer.step()

        current_loss = loss.item()
        losses.append(current_loss)

        if (epoch + 1) % 10 == 0:
            logger.info(f"Epoch {epoch + 1}/{epochs}, Loss: {current_loss:.4f}")

        # Early stopping check
        if early_stopping_patience > 0:
            if current_loss < best_loss - 1e-6:
                best_loss = current_loss
                best_state_dict = {k: v.clone() for k, v in model.state_dict().items()}
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= early_stopping_patience:
                    logger.info(
                        f"Early stopping at epoch {epoch + 1}: "
                        f"no improvement for {early_stopping_patience} epochs "
                        f"(best loss: {best_loss:.4f})"
                    )
                    break

    # Restore best model weights if early stopping was used
    if best_state_dict is not None:
        model.load_state_dict(best_state_dict)

    return model, losses


def get_embeddings(
    model: GraphSAGEModel,
    data: Data,
    device: Optional[str] = None,
) -> torch.Tensor:
    """
    Get embeddings for all nodes.

    Args:
        model: Trained GraphSAGE model
        data: Graph data
        device: Device to use

    Returns:
        Embedding matrix [num_nodes, output_dim]
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model = model.to(device)
    data = data.to(device)

    model.eval()
    with torch.no_grad():
        embeddings = model(data.x, data.edge_index)

    return embeddings.cpu()


def save_model(
    model: GraphSAGEModel,
    path: Path,
    metadata: Optional[dict] = None,
):
    """
    Save model to disk.

    Args:
        model: Model to save
        path: Save path
        metadata: Optional metadata to save
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    checkpoint = {
        "model_state_dict": model.state_dict(),
        "model_config": {
            "input_dim": model.convs[0].in_channels,
            "hidden_dim": model.convs[0].out_channels if len(model.convs) > 1 else None,
            "output_dim": model.convs[-1].out_channels,
            "num_layers": model.num_layers,
            "dropout": model.dropout,
        },
        "metadata": metadata or {},
    }

    torch.save(checkpoint, path)
    logger.info(f"Model saved to {path}")


def load_model(path: Path, device: Optional[str] = None) -> GraphSAGEModel:
    """
    Load model from disk.

    Args:
        path: Model path
        device: Device to load to

    Returns:
        Loaded model
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    checkpoint = torch.load(path, map_location=device)
    config = checkpoint["model_config"]

    model = GraphSAGEModel(
        input_dim=config["input_dim"],
        hidden_dim=config.get("hidden_dim", 64),
        output_dim=config["output_dim"],
        num_layers=config["num_layers"],
        dropout=config.get("dropout", 0.5),
    )

    model.load_state_dict(checkpoint["model_state_dict"])
    model = model.to(device)

    logger.info(f"Model loaded from {path}")
    return model
