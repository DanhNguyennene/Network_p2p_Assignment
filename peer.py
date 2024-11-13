from lib import *

TRACKER_URL = 'http://localhost:8000'

class PeerNode:
    def __init__(self, peer_id, ip, port, shared_files):
        self.peer_id = peer_id
        self.ip = ip
        self.port = port
        self.shared_files = shared_files
        self.downloaded_files = {}
        self.shutdown_event = threading.Event()
        self.server_socket = None
        self.lock = threading.Lock()

        # Initialize a thread pool for handling downloads and clients
        self.executor = ThreadPoolExecutor(max_workers=5)

    def register_with_tracker(self):
        """Registers the peer with the tracker."""
        data = {
            "peer_id": self.peer_id,
            "ip": self.ip,
            "port": self.port,
            "files": list(self.shared_files.keys())
        }
        try:
            response = requests.post(f"{TRACKER_URL}/announce", json=data)
            if response.status_code == 200:
                print(f"Registered with tracker: {response.json()}")
            else:
                print(f"Failed to register: {response.text}")
        except Exception as e:
            print(f"Error registering with tracker: {e}")

    def download_file(self, file_hash):
        """Downloads a file from other peers."""
        try:
            response = requests.get(f"{TRACKER_URL}/get_peers", params={"file_hash": file_hash})
            if response.status_code != 200:
                print("Failed to fetch peers.")
                return
            
            peers = response.json().get('peers', [])
            if not peers:
                print("No peers available for this file.")
                return
            
            # Use ThreadPoolExecutor to manage threads for downloads
            for peer in peers:
                self.executor.submit(self.request_file, peer['ip'], peer['port'], file_hash)
        except Exception as e:
            print(f"Error downloading file: {e}")

    def request_file(self, ip, port, file_hash):
        """Connects to a peer and requests a file."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(10)
                s.connect((ip, port))
                s.sendall(file_hash.encode())

                with open(f"downloaded_{file_hash}.dat", 'wb') as f:
                    while True:
                        ready = select.select([s], [], [], 5)
                        if ready[0]:
                            data = s.recv(1024)
                            if not data:
                                break
                            f.write(data)
                        else:
                            break
                print(f"File {file_hash} downloaded from {ip}:{port}")
        except (socket.timeout, socket.error, ConnectionResetError) as e:
            print(f"Error downloading file from {ip}:{port} - {e}")

    def start_server(self):
        """Starts a peer server to upload files to others."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.ip, self.port))
        self.server_socket.listen()
        print(f"Peer listening on {self.ip}:{self.port}")

        try:
            while not self.shutdown_event.is_set():
                self.server_socket.settimeout(1)
                try:
                    conn, addr = self.server_socket.accept()
                    self.executor.submit(self.handle_client, conn, addr)
                except socket.timeout:
                    continue
        except Exception as e:
            print(f"Error in server loop: {e}")
        finally:
            self.server_socket.close()

    def handle_client(self, conn, addr):
        """Handles file upload requests from other peers."""
        try:
            file_hash = conn.recv(1024).decode()
            with self.lock:
                if file_hash in self.shared_files:
                    file_path = self.shared_files[file_hash]
                    with open(file_path, 'rb') as f:
                        conn.sendfile(f)
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
        finally:
            conn.close()

    def shutdown(self):
        """Gracefully shutdown the server."""
        self.shutdown_event.set()
        self.executor.shutdown(wait=True)
        if self.server_socket:
            try:
                self.server_socket.shutdown(socket.SHUT_RDWR)
                self.server_socket.close()
            except Exception as e:
                print(f"Error closing server socket: {e}")

