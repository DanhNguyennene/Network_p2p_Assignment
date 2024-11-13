from lib import *


TRACKER_URL = 'http://localhost:8000'
PIECE_SIZE = 512 * 1024  # 512KB

class PeerNode:
    def __init__(self, peer_id, ip, port, file_path):
        self.peer_id = peer_id
        self.ip = ip
        self.port = port
        self.file_path = file_path
        self.pieces = self.split_file_into_pieces(file_path)
        self.shared_pieces = {i: True for i in range(len(self.pieces))}  # Dictionary to track pieces
        self.shutdown_event = threading.Event()
        self.server_socket = None
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=5)

    def split_file_into_pieces(self, file_path):
        """Split the file into pieces of size `PIECE_SIZE`."""
        pieces = []
        with open(file_path, 'rb') as f:
            while True:
                piece = f.read(PIECE_SIZE)
                if not piece:
                    break
                pieces.append(piece)
        return pieces

    def register_with_tracker(self):
        """Registers the peer with the tracker."""
        data = {
            "peer_id": self.peer_id,
            "ip": self.ip,
            "port": self.port,
            "num_pieces": len(self.pieces)
        }
        try:
            response = requests.post(f"{TRACKER_URL}/announce", json=data)
            if response.status_code == 200:
                print(f"Registered with tracker: {response.json()}")
            else:
                print(f"Failed to register: {response.text}")
        except Exception as e:
            print(f"Error registering with tracker: {e}")

    def download_piece(self, piece_index, peer_ip, peer_port):
        """Download a specific piece from another peer."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((peer_ip, peer_port))
                s.sendall(f"REQUEST_PIECE {piece_index}".encode())
                
                # Receive the piece
                piece_data = b''
                while True:
                    data = s.recv(1024)
                    if not data:
                        break
                    piece_data += data
                
                # Save the downloaded piece
                with open(f"downloaded_piece_{piece_index}.dat", 'wb') as f:
                    f.write(piece_data)
                print(f"Piece {piece_index} downloaded from {peer_ip}:{peer_port}")
        except Exception as e:
            print(f"Error downloading piece {piece_index} from {peer_ip}:{peer_port} - {e}")

    def start_server(self):
        """Starts a peer server to upload pieces to others."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.ip, self.port))
        self.server_socket.listen()
        print(f"Peer listening on {self.ip}:{self.port}")

        try:
            while not self.shutdown_event.is_set():
                conn, addr = self.server_socket.accept()
                self.executor.submit(self.handle_client, conn, addr)
        except Exception as e:
            print(f"Error in server loop: {e}")
        finally:
            self.server_socket.close()

    def handle_client(self, conn, addr):
        """Handles piece upload requests from other peers."""
        try:
            request = conn.recv(1024).decode()
            if request.startswith("REQUEST_PIECE"):
                piece_index = int(request.split()[1])
                if piece_index in self.shared_pieces:
                    piece_data = self.pieces[piece_index]
                    conn.sendall(piece_data)
                    print(f"Uploaded piece {piece_index} to {addr}")
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
        finally:
            conn.close()

    def shutdown(self):
        """Shutdown the peer server gracefully."""
        self.shutdown_event.set()
        self.executor.shutdown(wait=True)
        if self.server_socket:
            try:
                self.server_socket.shutdown(socket.SHUT_RDWR)
                self.server_socket.close()
            except Exception as e:
                print(f"Error closing server socket: {e}")

