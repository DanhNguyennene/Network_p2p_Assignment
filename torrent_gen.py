import os
import hashlib
import bencodepy


def get_files_in_directory(directory):
    """Recursively gets all files in the directory."""
    file_list = []
    for root, _, files in os.walk(directory):
        for file in files:
            full_path = os.path.join(root, file)
            relative_path = os.path.relpath(full_path, directory)
            file_list.append((relative_path, full_path))
    return file_list


def split_file(file_path, piece_size=512 * 1024):
    """
    Splits the file into pieces and returns a concatenated byte string
    of the SHA-1 hashes of each piece.
    """
    pieces = b""  # Initialize an empty bytes object to store all SHA-1 hashes
    file_size = os.path.getsize(file_path)
    if file_size < piece_size:
        piece = f.read()
        piece_hash = hashlib.sha1(piece).digest()
        pieces += piece_hash
        print(
            f"[DEBUG] File smaller than piece size: Size={len(piece)}, Hash={piece_hash.hex()}"
        )
        return pieces
    piece_sizes = []
    with open(file_path, "rb") as f:
        index = 0
        while True:

            piece = f.read(piece_size)
            piece_sizes.append(len(piece))
            if not piece:
                break

            # Calculate the SHA-1 hash of the piece
            piece_hash = hashlib.sha1(piece).digest()

            # Concatenate the hash to the pieces byte string
            pieces += piece_hash
            print(
                f"[DEBUG] Split piece {index}: Size={len(piece)}, Hash={piece_hash.hex()}"
            )
            index += 1

        # Check if there's any leftover data not perfectly divisible by piece_size
        if len(piece) > 0 and len(piece) < piece_size:
            print(f"[DEBUG] Final leftover piece added: Size={len(piece)}")
            piece_hash = hashlib.sha1(piece).digest()
            pieces += piece_hash

    return pieces, piece_sizes


def generate_torrent(directory, tracker_url, output_path, piece_size=512 * 1024):
    """Generates a .torrent file for the specified directory."""
    files = get_files_in_directory(directory)
    print(files)

    pieces = []
    total_length = 0
    file_info_list = []
    last_piece_sizes_dict = {
        "path": [],
        "length": [],
    }
    # Process each file in the directory
    for relative_path, full_path in files:
        file_size = os.path.getsize(full_path)
        total_length += file_size

        # Calculate the pieces for the current file
        file_pieces, pieces_sizes = split_file(full_path, piece_size)
        print(file_pieces)
        pieces.append(file_pieces)
        last_piece_sizes_dict["path"].append(relative_path)
        last_piece_sizes_dict["length"].append(
            pieces_sizes[-2]
        )  # -2 beacuse last piece is already is just 0
        # Add file info to the list
        file_info_list.append(
            {"length": file_size, "path": relative_path.split(os.sep)}
        )

    # Create the torrent metadata
    torrent_info = {
        "announce": tracker_url,
        "info": {
            "files": file_info_list,
            "name": os.path.basename(directory),
            "piece length": piece_size,
            "last piece length": last_piece_sizes_dict,
            "pieces": b"".join(pieces),
        },
    }

    # Encode the metadata using Bencode
    encoded_torrent = bencodepy.encode(torrent_info)

    # Write the .torrent file
    torrent_file_path = os.path.join(
        output_path, f"{os.path.basename(directory)}.torrent"
    )
    with open(torrent_file_path, "wb") as f:
        f.write(encoded_torrent)

    print(f"Torrent file generated: {torrent_file_path}")


if __name__ == "__main__":
    directory = "./shared"
    output_path = "torrents"
    os.makedirs(output_path, exist_ok=True)
    generate_torrent(directory, "http://localhost:8000/announce", output_path)
    torrent_file = "./torrents/" + "shared.torrent"
    with open(torrent_file, "rb") as f:
        torrent_data = bencodepy.decode(f.read())
    print(torrent_data)
