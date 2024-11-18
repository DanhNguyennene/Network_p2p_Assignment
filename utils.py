from lib import *

def get_files_in_directory(directory):
    """Recursively gets all files in the directory."""
    # Convert the directory path to an absolute path and normalize it
    directory = os.path.abspath(directory)
    directory = os.path.normpath(directory)
    
    file_list = []

    # Walk through the directory and gather all files
    for cur_dir, _, files in os.walk(directory):
        cur_dir = os.path.normpath(cur_dir)
        for file in files:
            full_path = os.path.normpath(os.path.join(cur_dir, file))
            relative_path = os.path.relpath(full_path, directory)
            
            # Append the relative path and the full path to the file_list
            file_list.append((relative_path, full_path))
    
    return file_list


def split_path(path):
    parts = []
    while True:
        path, tail = os.path.split(path)
        if tail:
            parts.insert(0, tail)
        else:
            if path:
                parts.insert(0, path)
            break
    return parts


def split_file(file_path, piece_size=512 * 1024):
    """
    Splits the file into pieces and returns a concatenated byte string
    of the SHA-1 hashes of each piece.
    """
    pieces = b""  # Initialize an empty bytes object to store all SHA-1 hashes
    piece_sizes = []
    file_size = os.path.getsize(file_path)

    if file_size < piece_size:
        with open(file_path, "rb") as f:
            piece = f.read() 
            hash_piece = hashlib.sha1(piece).digest()
            pieces += hash_piece

        print(
            f"[DEBUG] File smaller than piece size: Size={len(piece)}, Hash={hash_piece.hex()}"
        )
        return pieces

    with open(file_path, "rb") as f:
        index = 0
        while True:
            piece = f.read(piece_size)
            if not piece:
                break
            piece_sizes.append(len(piece))

            # Calculate the SHA-1 hash of the piece
            hash_piece = hashlib.sha1(piece).digest()

            # Concatenate the hash to the pieces byte string
            pieces += hash_piece
            print(
                f"[DEBUG] Split piece {index}: Size={len(piece)}, Hash={hash_piece.hex()}"
            )
            index += 1

    return pieces


def generate_torrent(directory, tracker_url, output_path, piece_size=512 * 1024):
    """Generates a .torrent file for the specified directory."""
    file_paths = get_files_in_directory(directory)
    print(f"[DEBUG] Found {file_paths} files in directory: {directory}")
    pieces = []
    files = []

    # Process each file in the directory
    for relative_path, full_path in file_paths:
        file_length = os.path.getsize(full_path)

        # Calculate the pieces for the current file
        hash_piece = split_file(full_path, piece_size)
        pieces.append(hash_piece)
        files.append(
            {
                "length": file_length,
                "path": relative_path,
            }
        )
#  -------------------   
    # Create the torrent metadata
    torrent_info = {
        "announce": tracker_url,
        "info": {
            "piece_length": piece_size,
            "pieces": b"".join(pieces),
            "name": os.path.basename(os.path.normpath(directory)),
            "files": files,
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

    # print(f"Torrent file generated: {torrent_file_path}")
    # print(f"Info content: ")
    # for key, value in torrent_info["info"].items():
    #     print(f"{key}: {value}")
    #     if key == "files":
    #         for file in torrent_info["info"]["files"]:
    #             for fkey, fvalue in file.items():
    #                 print(f"{fkey}: {fvalue}")

    # print(f"Hash size: {len(torrent_info['info']['pieces'])}")
