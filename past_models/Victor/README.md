# Victor

Victor is the neural-network chess agent preserved from the `update_viktor` branch at
commit `e2a8047`. The runtime agent combines a trained position-evaluation network with
a fixed-depth negamax search and alpha-beta pruning.

The model was trained by Victor using positions labelled by Stockfish. Stockfish is not
part of the runtime agent. The dataset-generation scripts are retained only to document
and reproduce the offline training process.

## Files

- `agent.py` is the competition-compatible entry point.
- `transform_data.py` converts a FEN position into the network's 768 input features.
- `eval_net.onnx` and `eval_net.onnx.data` are the model used at runtime.
- `eval_net.pt` is the saved PyTorch training checkpoint.
- `train.py` defines and trains the network, then exports the ONNX model.
- `data/generate_stockfish_dataset.py` is the original single-process data generator.
- `data/generate_dataset_cores.py` is the original multi-process data generator.
- `data/.gitignore` keeps regenerated datasets out of version control.

The generated dataset itself was ignored by Git and was not present on the branch, so
it is not included here. The data-generation scripts contain Victor's original local
Windows Stockfish path and must be configured before they can reproduce the dataset.

## Local benchmark recorded by Victor

Victor recorded a 20-game arena against `baselines/greedy`:

```text
2 wins, 17 draws, 1 loss
52.5% chess score
```

This result used the normal starting position. It is a small sample and should not be
treated as an Elo estimate.

## Testing against Victor

From the repository root, compare the current root agent against this fixed opponent:

```bash
v-env/bin/python -m harness.arena \
    --agent . \
    --opponent past_models/Victor \
    --games 20 \
    --base-ms 120000 \
    --increment-ms 500
```

The model path in `agent.py` is resolved relative to this directory so the harness can
be launched normally from the repository root.

## Known limitations

- The network input encodes piece placement but not the side to move, castling rights,
  en-passant state, or move counters.
- Search depth is fixed from the remaining-clock threshold rather than managed with a
  deadline and iterative deepening.
- Moves are searched in python-chess's default order rather than tactical move order.
- The ONNX evaluator is much slower per position than Benjamin's material evaluation,
  so Victor searches fewer plies.

Keep this directory fixed while comparing future agents against Victor. The normal
submission packager includes the root agent and does not package `past_models/`.
