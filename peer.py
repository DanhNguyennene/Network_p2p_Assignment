from lib import *
from torrent import *
from message import *


class Peer:
    def __init__(
        self,
        torrent,
        client_id,
        ip,
        port,
        is_seeder=False,
    ):
        self.peer_id = self._create_peer_id(client_id)
        self.ip = ip
        self.port = port
        self.is_seeder = is_seeder
        self.server_socket = None

        self.downloaded = 0
        self.uploaded = 0

        self.am_choking = 1
        self.am_interested = 0
        self.peer_choking = 1
        self.peer_interested = 0

        self.executor = ThreadPoolExecutor(max_workers=10)
        self.shutdown_event = threading.Event()

        self.tracker_url = torrent.tracker_url
        self.name = torrent.name
        self.piece_length = torrent.piece_length
        self.info_hash = torrent.info_hash
        self.info = torrent.info

        self.message_factory = MessageFactory()
        self.message_parser = MessageParser()

        os.makedirs("downloads", exist_ok=True)
        os.makedirs("shared", exist_ok=True)

    def _create_peer_id(self, client_id, version_number="1000"):
        if (
            len(client_id) != 2
            or not any(c.isdigit() for c in client_id)
            or not any(c.isalpha() for c in client_id)
        ):
            raise ValueError("Client ID containing 2 letters or numbers")
        if len(version_number) != 4 or not version_number.isdigit():
            raise ValueError("Version number must be exactly four digits")

        random_part = "".join(random.choices(string.digits, k=8))

        peer_id = f"-{client_id.upper()}{version_number}-{random_part}-"

        return peer_id

    def register_with_tracker(self):
        """Register with the tracker and get a list of peers."""
        data = {
            "info_hash": self.info_hash,
            "peer_id": self.peer_id,
            "ip": self.ip,
            "port": self.port,
            "downloaded": self.downloaded,
            "uploaded": self.uploaded,
            "is_seeder": self.is_seeder,
        }
        try:
            response = requests.post(self.tracker_url + "announce", json=data)
            return response.json()
        except requests.RequestException as e:
            print(f"[ERROR] registering with tracker: {e}")
            return []

    def get_peers(self):
        """Get the list of peers from the tracker"""
        data = {
            "info_hash": self.info_hash,
        }
        try:
            response = requests.get(self.tracker_url + "get_peers", json=data)
            return response.json()
        except request.RequestException as e:
            print(f"[ERROR] fetching data from tracker: {e}")

    def start_server(self):
        """Start the peer server to handle piece requests."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.ip, self.port))
        self.server_socket.listen()
        print(f"Peer {self.peer_id} listening on {self.ip}:{self.port}")

        try:
            while not self.shutdown_event.is_set():
                conn, addr = (
                    self.server_socket.accept()
                )  # block until receive a request
                self.executor.submit(
                    self.handle_client, conn, addr
                )  # threading running the handle_client function
        except Exception as e:
            print(f"Error in server: {e}")
        finally:
            self.server_socket.close()

    def handle_client(self, conn, addr):
        """Handles requests for specific pieces from other peers."""
        request = conn.recv(1024)

        data = self.message_parser.parse_message(request)
        response = self.message_factory.handshake(
            self.info_hash, self.peer_id.encode("utf-8")
        )
        conn.sendall(response)
        # elif type == "message":
        # data = self.message_parser.parse_message(request)

        return data

    def get_piece(self, file_path, index):
        """Retrieve a piece by index for a specific file."""
        try:
            start = index * self.piece_length
            with open(file_path, "rb") as f:
                f.seek(start)
                data = f.read(self.piece_length)
            print(f"[DEBUG] File path: {file_path}, from peer: {self.peer_id}")
            # print(f"[DEBUG] Data: {data}")
            print(f"[DEBUG] Read piece {index} from {file_path}, length: {len(data)}")
            return data
        except Exception as e:
            print(f"[ERROR] Error reading piece {index} from {file_path}: {e}")
            return b""

    def download_piece(self, peer_ip, peer_port):
        """Download a specific piece from a peer."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((peer_ip, peer_port))

            # Handshaking
            handshake = self.message_factory.handshake(
                self.info_hash, self.peer_id.encode("utf-8")
            )
            client_socket.sendall(handshake)
            response = client_socket.recv(1024)

            # Sending HAVE message
            have = self.message_factory.have(piece_index=1)

            # Sending CHOKE/UNCHOKE INTERESTED/NOT INTERESTED
            self.am_interested = 1
            client_socket.sendall(self.am_interested)

    def save_piece(self, file_path, index, data):
        """Save a piece to the file."""
        try:
            start = index * self.piece_length
            with open(file_path, "r+b") as f:
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
