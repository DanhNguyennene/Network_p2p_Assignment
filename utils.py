from lib import *
import socket
def get_files_in_directory(directory):
    """Recursively gets all files in the directory with improved cross-platform handling."""
    # Use Path for robust cross-platform path handling
    directory = Path(directory).resolve()

    file_list = []

    # Walk through the directory and gather all files
    for cur_dir, _, files in os.walk(directory):
        cur_dir = Path(cur_dir)
        for file in files:
            full_path = cur_dir / file
            relative_path = full_path.relative_to(directory)

            # Ensure paths use forward slashes for consistency
            file_list.append((str(relative_path).replace(os.path.sep, '/'), 
                              str(full_path)))

    return file_list


def split_path(path):
    """Split path in a cross-platform manner."""
    return Path(path).parts


def split_file(file_path, piece_size=512 * 1024):
    """
    Splits the file into pieces and returns a concatenated byte string
    of the SHA-1 hashes of each piece with improved error handling.
    """
    pieces = b""  # Initialize an empty bytes object to store all SHA-1 hashes
    piece_sizes = []
    
    try:
        file_size = os.path.getsize(file_path)

        with open(file_path, "rb") as f:
            if file_size <= piece_size:
                piece = f.read()
                hash_piece = hashlib.sha1(piece).digest()
                pieces += hash_piece
                return pieces

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
                index += 1

        return pieces

    except (IOError, OSError) as e:
        print(f"[ERROR] Error processing file {file_path}: {e}")
        return b""


def generate_torrent(
    directory,
    files_directory,
    tracker_url,
    output_name,
    piece_size=512 * 1024,
):
    """Generates a .torrent file for the specified directory with robust cross-platform support."""
    # Use Path for consistent directory handling
    directory = Path(directory)
    files_directory = Path(files_directory)
    
    # Ensure directory exists
    directory.mkdir(parents=True, exist_ok=True)
    
    file_paths = get_files_in_directory(files_directory)
    
    pieces = []
    files = []

    # Process each file in the directory
    for relative_path, full_path in file_paths:
        try:
            file_length = os.path.getsize(full_path)

            # Calculate the pieces for the current file
            hash_piece = split_file(full_path, piece_size)
            pieces.append(hash_piece)
            files.append(
                {
                    "length": file_length,
                    "path": relative_path.split('/'),  # Use list of path components
                }
            )
        except Exception as e:
            print(f"[ERROR] Skipping file {full_path}: {e}")

    # Create the torrent metadata
    torrent_info = {
        "announce": tracker_url,
        "info": {
            "piece_length": piece_size,
            "pieces": b"".join(pieces),
            "name": files_directory.name,  # Consistent and cross-platform
            "files": files,  # Already sorted during processing
        },
    }

    # Encode the metadata using Bencode
    encoded_torrent = bencodepy.encode(torrent_info)

    # Write the .torrent file
    torrent_file_path = directory / output_name
    
    try:
        with open(torrent_file_path, "wb") as f:
            f.write(encoded_torrent)
        print(f"Torrent file generated: {torrent_file_path}")
    except Exception as e:
        print(f"[ERROR] Failed to write torrent file: {e}")

def get_actual_ip():
    """Retrieve the actual IP address of the machine"""
    hostname = socket.gethostname()
    return socket.gethostbyname(hostname)
def generate_peer_info(num_peer):
    peer_info = {}
    peer_ip = get_actual_ip()
    for i in range(num_peer):
        peer_id = generate_peer_id(f"A{i+1}")
        peer_port = 6881 + i
        directory = f"peer_A{i+1}_{peer_ip}"
        files_directory = "TO_BE_SHARED"

        peer_info[peer_id] = {
            "address": (peer_ip, peer_port),
            "directory": directory,
            "files_directory": Path(os.path.join(directory, files_directory)).as_posix(),
        }

    return peer_info

IP = "192.168.2.156"
def generate_tracker_info():
    tracker_info = {"url": f"http://{IP}:8000/"}

    return tracker_info


def generate_peer_id(client_id, version_number="1000"):
    if (
        not any(c.isdigit() for c in client_id)
        or not any(c.isalpha() for c in client_id)
    ):
        raise ValueError("Client ID containing 2 letters or numbers")

    random_part = "".join(random.choices(string.digits, k=8))

    peer_id = f"-{client_id.upper()}{version_number}-{random_part}-"

    return peer_id
