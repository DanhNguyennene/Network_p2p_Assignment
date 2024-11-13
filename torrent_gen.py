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
    """Splits the file into pieces and returns a list of SHA-1 hashes."""
    with open(file_path, 'rb') as f:
        while True:
            piece = f.read(piece_size)
            if not piece:
                break
            yield hashlib.sha1(piece).digest()

def generate_torrent(directory, tracker_url, output_path, piece_size=512 * 1024):
    """Generates a .torrent file for the specified directory."""
    files = get_files_in_directory(directory)
    
    pieces = []
    total_length = 0
    file_info_list = []

    # Process each file in the directory
    for relative_path, full_path in files:
        file_size = os.path.getsize(full_path)
        total_length += file_size

        # Calculate the pieces for the current file
        for piece in split_file(full_path, piece_size):
            pieces.append(piece)

        # Add file info to the list
        file_info_list.append({
            "length": file_size,
            "path": relative_path.split(os.sep)
        })

    # Create the torrent metadata
    torrent_info = {
        "announce": tracker_url,
        "info": {
            "files": file_info_list,
            "name": os.path.basename(directory),
            "piece length": piece_size,
            "pieces": b''.join(pieces)
        }
    }

    # Encode the metadata using Bencode
    encoded_torrent = bencodepy.encode(torrent_info)

    # Write the .torrent file
    torrent_file_path = os.path.join(output_path, f"{os.path.basename(directory)}.torrent")
    with open(torrent_file_path, 'wb') as f:
        f.write(encoded_torrent)
    
    print(f"Torrent file generated: {torrent_file_path}")

if __name__ == "__main__":
    directory = "shared"
    output_path = "torrents"
    os.makedirs(output_path, exist_ok=True)
    generate_torrent(directory, "http://localhost:8000/announce", output_path)