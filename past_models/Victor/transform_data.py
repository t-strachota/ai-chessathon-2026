"""
Processes a FEN string (chess move data) into a 773-length vector of 0s and 1s.
There are 64 squares and 12 planes, one for each colour and piece combination,
plus side to move and 4 castling rights flags.

Order of planes: white P N B R Q K, black p n b r q k
In each plane, index = number of square. Matches import chess
"""

import chess
import numpy as np

# ------- Convert fen to digits --------
# Pieces
PIECE_TO_DIGIT = {
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


# transform the rest of the fen
def transform_fen(fen: str) -> np.ndarray:
    board = chess.Board(fen)
    vec = np.zeros(773, dtype=np.float32)

    for square, piece in board.piece_map().items():
        plane = PIECE_TO_DIGIT[piece.symbol()]
        vec[plane * 64 + square] = 1.0

    vec[768] = 1.0 if board.turn == chess.WHITE else 0.0
    vec[769] = 1.0 if board.has_kingside_castling_rights(chess.WHITE) else 0.0
    vec[770] = 1.0 if board.has_queenside_castling_rights(chess.WHITE) else 0.0
    vec[771] = 1.0 if board.has_kingside_castling_rights(chess.BLACK) else 0.0
    vec[772] = 1.0 if board.has_queenside_castling_rights(chess.BLACK) else 0.0

    return vec


if __name__ == "__main__":
    # Check encoding was successful and correct
    start_fen = chess.STARTBOARD_FEN if hasattr(chess, "STARTBOARD_FEN") else chess.STARTING_FEN
    vec = transform_fen(chess.Board().fen())
    print("Encoded Length:", len(vec))  # Check length
    print("Total pieces on board (should be 32):", int(vec[:768].sum()))  # Check piece amount
    print("White pawn plane (a2-h2 should be 1s):", vec[8:16])  # Check white pawns
    print("Side to move (should be 1.0):", vec[768])
    print("Castling rights (should all be 1.0):", vec[769:773])