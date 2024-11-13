import socket
import threading
import os
import bencodepy
import requests
from concurrent.futures import ThreadPoolExecutor
from collections import deque

class PeerNode:
    def __init__(self, torrent_file, peer_id, ip, port, is_seeder=False):
        self.peer_id = peer_id
        self.ip = ip
        self.port = port
        self.is_seeder = is_seeder
        self.load_torrent(torrent_file)
        self.server_socket = None
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.shutdown_event = threading.Event()
        self.downloaded = 0
        self.uploaded = 0

        # Initialize pieces tracking for multiple files
        self.pieces_downloaded = {file['path']: [False] * file['num_pieces'] for file in self.files}

        os.makedirs("downloads", exist_ok=True)
        os.makedirs("shared", exist_ok=True)
    def create_file_or_directory(self, file_info):
        """Create a file or directory based on the metadata from the .torrent file."""
        try:
            decoded_path = [part.decode() for part in file_info[b"path"]]
            file_path = os.path.join("downloads", *decoded_path)
            file_size = file_info[b"length"]

            # Check if it's a directory or a file
            if file_path.endswith(os.sep):
                os.makedirs(file_path, exist_ok=True)
                print(f"[DEBUG] Created directory: {file_path}")
            else:
                # Ensure the parent directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Create an empty file if it doesn't exist
                if not os.path.isfile(file_path):
                    with open(file_path, 'wb') as f:
                        pass  # Create an empty file without using truncate()
                    print(f"[DEBUG] Created empty file: {file_path}")

                # Check the file size
                actual_size = os.path.getsize(file_path)
                if actual_size != file_size:
                    print(f"[WARNING] File {file_path} has size {actual_size}, expected {file_size}")
        except Exception as e:
            print(f"[ERROR] Error creating file or directory: {e}")


    def load_torrent(self, torrent_file):
        """Load metadata from the .torrent file."""
        with open(torrent_file, 'rb') as f:
            torrent_data = bencodepy.decode(f.read())
        
        self.tracker_url = torrent_data[b"announce"].decode()
        self.piece_length = torrent_data[b"info"][b"piece length"]
        self.pieces = torrent_data[b"info"][b"pieces"]
        self.num_pieces = len(self.pieces) // 20
        self.files = []

        # Load files metadata and create necessary files/directories
        for file_info in torrent_data[b"info"][b"files"]:
            # Debugging statement to inspect file_info structure
            print(f"[DEBUG] file_info: {file_info}")
            
            # Ensure the 'path' key exists
            if b"path" not in file_info:
                print(f"[ERROR] Missing 'path' in file_info: {file_info}")
                continue
            
            # Ensure the 'length' key exists
            if b"length" not in file_info:
                print(f"[ERROR] Missing 'length' in file_info: {file_info}")
                continue
            
            # Decode the path components and add to files list
            decoded_path = [part.decode() for part in file_info[b"path"]]
            file_path = os.path.join("downloads", *decoded_path)
            file_size = file_info[b"length"]

            # Create file or directory
            self.create_file_or_directory(file_info)
            self.files.append({
                "path": file_path,
                "length": file_size,
                "num_pieces": (file_size + self.piece_length - 1) // self.piece_length
            })

                                            
    def register_with_tracker(self):
        """Register with the tracker and get a list of peers."""
        data = {
            "peer_id": self.peer_id,
            "ip": self.ip,
            "port": self.port,
            "file_hash": self.pieces.hex(),
            "downloaded": self.downloaded,
            "uploaded": self.uploaded,
            "is_seeder": self.is_seeder
        }
        try:
            response = requests.post(self.tracker_url, json=data)
            return response.json()
        except requests.RequestException as e:
            print(f"Error communicating with tracker: {e}")
            return []

    def start_server(self):
        """Start the peer server to handle piece requests."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.ip, self.port))
        self.server_socket.listen()
        print(f"Peer {self.peer_id} listening on {self.ip}:{self.port}")

        try:
            while not self.shutdown_event.is_set():
                conn, addr = self.server_socket.accept()
                self.executor.submit(self.handle_client, conn, addr)
        except Exception as e:
            print(f"Error in server: {e}")
        finally:
            self.server_socket.close()

    def handle_client(self, conn, addr):
        """Handles requests for specific pieces from other peers."""
        try:
            request = conn.recv(1024).decode()
            if request.startswith("REQUEST_PIECE"):
                file_path, piece_index = request.split()[1], int(request.split()[2])
                piece_data = self.get_piece(file_path, piece_index)
                conn.sendall(piece_data)
                self.update_upload_stats(len(piece_data))
                print(f"Uploaded piece {piece_index} of {file_path} to {addr}")
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
        finally:
            conn.close()

    def get_piece(self, file_path, index):
        """Retrieve a piece by index for a specific file."""
        try:
            start = index * self.piece_length
            with open(file_path, 'rb') as f:
                f.seek(start)
                data = f.read(self.piece_length)
            print(f"[DEBUG] Read piece {index} from {file_path}, length: {len(data)}")
            return data
        except Exception as e:
            print(f"[ERROR] Error reading piece {index} from {file_path}: {e}")
            return b''


    def download_piece(self, file_path, piece_index, peer_ip, peer_port):
        """Download a specific piece from a peer."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((peer_ip, peer_port))
                s.sendall(f"REQUEST_PIECE {file_path} {piece_index}".encode())

                # Download the full piece in chunks
                piece_data = b''
                while len(piece_data) < self.piece_length:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    piece_data += chunk
                
                if len(piece_data) == self.piece_length:
                    self.save_piece(file_path, piece_index, piece_data)
                    self.update_download_stats(len(piece_data))
                    print(f"Downloaded piece {piece_index} of {file_path} from {peer_ip}:{peer_port}")
        except Exception as e:
            print(f"Error downloading piece {piece_index} of {file_path} from {peer_ip}:{peer_port}: {e}")

    def save_piece(self, file_path, index, data):
        """Save a piece to the file."""
        try:
            start = index * self.piece_length
            with open(file_path, 'r+b') as f:
                f.seek(start)
                f.write(data)
            self.pieces_downloaded[file_path][index] = True
            print(f"[DEBUG] Saved piece {index} to {file_path}, length: {len(data)}")
        except Exception as e:
            print(f"[ERROR] Error saving piece {index} to {file_path}: {e}")


    def update_download_stats(self, bytes_downloaded):
        self.downloaded += bytes_downloaded
        self.register_with_tracker()

    def update_upload_stats(self, bytes_uploaded):
        self.uploaded += bytes_uploaded
        self.register_with_tracker()

    def shutdown(self):
        self.shutdown_event.set()
        self.executor.shutdown(wait=True)
        if self.server_socket:
            try:
                self.server_socket.shutdown(socket.SHUT_RDWR)
                self.server_socket.close()
            except Exception as e:
                print(f"Error closing server socket: {e}")
