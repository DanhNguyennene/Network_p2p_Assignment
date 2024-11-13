import os

def split_file(file_path, piece_size=512*1024):
    """Split the file into pieces of size `piece_size` bytes."""
    file_size = os.path.getsize(file_path)
    pieces = []

    with open(file_path, 'rb') as f:
        while True:
            piece = f.read(piece_size)
            if not piece:
                break
            pieces.append(piece)
    
    return pieces

def save_piece(piece, piece_index, output_dir="pieces"):
    """Save a piece to the specified output directory."""
    os.makedirs(output_dir, exist_ok=True)
    piece_path = os.path.join(output_dir, f"piece_{piece_index}.dat")
    with open(piece_path, 'wb') as f:
        f.write(piece)
    return piece_path
