"""
Trains MLP (multi-layer perceptron) from 768 nuerons to 1 neuron currently, to best predict
Stockfish evaluation if it were to play from the board position.

Reads full_dataset.json, encodes/transforms positions from FEN, trains, and saves
a PyTorch checkpoint and ONNX export for comp style.
"""

import json
import time

import chess
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

# Encoder digits
PIECE_TO_DIGITS = {
    "P": 0,
    "N": 1,
    "B": 2,
    "R": 3,
    "Q": 4,
    "K": 5,
    "p": 6,
    "n": 7,
    "b": 8,
    "r": 9,
    "q": 10,
    "k": 11,
}

CP_CLAMP = 1000  # positions beyond +- 1000 centipawns (score) are clamped
# at 1000. This is so the network doesnt follow alot from just one extreme example
# See line 50-60


# transform the rest of the fen
def transform_fen(fen: str) -> np.ndarray:
    board = chess.Board(fen)
    planes = np.zeros(768, dtype=np.float32)

    for square, piece in board.piece_map().items():
        plane = PIECE_TO_DIGITS[piece.symbol()]
        planes[plane * 64 + square] = 1.0

    return planes


class ChessDataset(Dataset):
    """
    Loads data into mem once
    """

    def __init__(self, jsonl_path):
        fens = []
        cps = []  # Centipawns - score system used by py chess.
        # 100 centipawns is score 1 for winner (you). -20 is 0.2 score for op

        # Read data file
        with open(jsonl_path) as f:
            for line in f:
                obj = json.loads(line)
                fens.append(obj["fen"])
                cps.append(obj["cp"])

        print(f"Reading & Encoding {len(fens)} positions...")
        self.X = np.stack([transform_fen(f) for f in fens])

        # Clamp extreme cp values. Will be scaled to [1,-1].
        # Avoids extreme postitions dominating the learning of the network
        cps = np.clip(np.array(cps, dtype=np.float32), -CP_CLAMP, CP_CLAMP)
        self.y = (cps / CP_CLAMP).astype(np.float32)  # normalize

        print(f"Complete. X shape {self.X.shape}, y shape {self.y.shape}")
        # X is the input to the network, y is the output

    def __len__(self):
        return len(self.y)

    def __getitem__(self, index):
        return self.X[index], self.y[index]


class EvalNet(nn.Module):
    """
    The MLP. 768 inputs -> 256 -> 32 -> 1 output
    Uses tanh, used predictions between [-1,1]
    """

    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(768, 256),
            nn.ReLU(),
            nn.Linear(256, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Tanh(),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)
        # The squeeze removes trailing 1 in the data


# lr is learning rate (higher then learns in shorter steps), batch_size is data per step
# epochs is number of times network iterates through data
def train(dataset_path, epochs=10, batch_size=256, lr=1e-3, val_fraction=0.1):
    full_dataset = ChessDataset(dataset_path)

    # Split into train/validation sets. Fixed seed so the split is
    # reproducible -- rerunning gives you the same split, not a new
    # random one each time, which matters for comparing runs fairly.
    n = len(full_dataset)
    n_val = int(n * val_fraction)
    n_train = n - n_val

    generator = torch.Generator().manual_seed(42)
    train_set, val_set = torch.utils.data.random_split(
        full_dataset, [n_train, n_val], generator=generator
    )
    print(f"Split: {n_train} training, {n_val} validation positions")

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=batch_size, shuffle=False)

    model = EvalNet()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    # Tracks best epoch to use instead of overfitting extra epochs
    best_val_loss = float("inf")
    best_state = None

    overall_start = time.time()
    for epoch in range(epochs):
        # --- Training pass ---
        model.train()
        total_train_loss = 0.0
        for x_batch, y_batch in train_loader:
            optimizer.zero_grad()
            preds = model(x_batch)
            loss = loss_fn(preds, y_batch)
            loss.backward()
            optimizer.step()
            total_train_loss += loss.item() * len(x_batch)
        avg_train_loss = total_train_loss / n_train

        # --- Validation pass: no learning happens here, just measuring ---
        model.eval()
        total_val_loss = 0.0
        with torch.no_grad():
            for x_batch, y_batch in val_loader:
                preds = model(x_batch)
                loss = loss_fn(preds, y_batch)
                total_val_loss += loss.item() * len(x_batch)

        # Records loss, and keep track of best epoch
        avg_val_loss = total_val_loss / n_val
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_state = model.state_dict()

        elapsed_total = time.time() - overall_start
        avg_epoch_time = elapsed_total / (epoch + 1)
        eta_seconds = avg_epoch_time * (epochs - (epoch + 1))
        eta_min, eta_sec = divmod(int(eta_seconds), 60)

        print(
            f"Epoch {epoch + 1}/{epochs}"
            f"train_loss={avg_train_loss:.5f}  val_loss={avg_val_loss:.5f}"
            f"({avg_epoch_time:.1f}s/epoch, ETA {eta_min}m {eta_sec}s)"
        )

    print(f"Best validation loss: {best_val_loss:.5f} (restoring those weights)")
    model.load_state_dict(best_state)
    return model


# Exports data into an onnx file format
def export_onnx(model, path="eval_net.onnx"):
    model.eval()
    temp_input = torch.zeros(1, 768)
    torch.onnx.export(
        model,
        temp_input,
        path,
        input_names=["board"],
        output_names=["eval"],
        dynamic_axes={"board": {0: "batch"}, "eval": {0: "batch"}},
    )
    print(f"Exported to {path}")


if __name__ == "__main__":
    model = train("../../data/full_dataset.jsonl", epochs=10, batch_size=64)
    torch.save(model.state_dict(), "eval_net.pt")
    export_onnx(model)
