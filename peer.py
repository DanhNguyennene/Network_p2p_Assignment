from lib import *
from torrent import *
from message import *
from peerqueue import DownloadQueue
from piecemanager import PieceManager

class Peer:
    def __init__(
        self,
        torrent,
        client_id,
        ip,
        port,
        is_seeder=False,
        shared_dir="./TO_BE_SHARED",
        downloaded_dir="./downloads",
    ):
        self.peer_id = self._create_peer_id(client_id)
        self.ip = ip
        self.port = port
        self.is_seeder = is_seeder
        self.server_socket = None

        self.downloaded = 0
        self.uploaded = 0

        self.shared_dir = shared_dir
        self.downloaded_dir = downloaded_dir
        print("INITIALIZING PIECE MANAGER FOR SEED")
        self.piece_manager_seed = PieceManager(torrent,self.shared_dir)
        print("INITIALIZING PIECE MANAGER FOR LEECH")
        self.piece_manager_leech = PieceManager(torrent,self.downloaded_dir)
        self.download_queue = DownloadQueue(self.piece_manager_seed.get_total_pieces())

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
            "info_hash": self.info_hash.hex(),
            "peer_id": self.peer_id,
            "ip": self.ip,
            "port": self.port,
            "downloaded": self.downloaded,
            "uploaded": self.uploaded,
            "is_seeder": self.is_seeder,
        }
        try:
            print(f"[DEBUG] Registering with tracker: {self.tracker_url + "announce"}")  
            response = requests.post(self.tracker_url + "announce", json=data)
            return response
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
        peer_id = addr
        print(f"Accepted connection from {addr}")

        try:
            # Step 1: Receive handshake and send response
            request = conn.recv(1024)
            data = self.message_parser.parse_message(request)
            if data is None or data["type"] != "handshake":
                print(f"[ERROR] Invalid handshake from {addr}")
                return

            # Send handshake response
            response = self.message_factory.handshake(self.info_hash, self.peer_id.encode())
            conn.sendall(response)
            print(f"[INFO] Handshake with {addr} completed")

            # Step 2: Initialize bitfield if received
            peer_bitfield = None

            # Step 3: Handle messages from the peer
            while True:
                try:
                    request = conn.recv(1024)

                    # Handle connection closure
                    if not request:
                        print(f"[INFO] Connection closed by peer {addr}")
                        break

                    data = self.message_parser.parse_message(request)
                    if data is None:
                        print(f"[ERROR] Received invalid message from {addr}")
                        continue

                    # Handle "keep-alive" message
                    if data["type"] == "keep-alive":
                        print(f"[DEBUG] Received keep-alive from {addr}")
                        continue

                    # Handle "handshake" message
                    if data["type"] == "handshake":
                        print(f"[INFO] Received handshake from {addr}")
                        continue

                    # Handle "bitfield" message
                    if data["type"] == "bitfield":
                        peer_bitfield = data["bitfield"]
                        peer_bitfield = self.message_factory.bitfield(peer_bitfield)
                        print(f"[INFO] Received bitfield from {addr}")
                        self.download_queue.update_bitfield(peer_id, peer_bitfield)
                        continue

                    # Handle "interested" message
                    if data["type"] == "interested":
                        self.download_queue.add_interested_peer(peer_id)
                        if self.download_queue.unchoke_peer(peer_id):
                            print(f"[INFO] Unchoking peer {addr}")
                            unchoke_msg = self.message_factory.unchoke()
                            conn.sendall(unchoke_msg)
                        else:
                            print(f"[INFO] Capacity reached. Unable to unchoke {addr}")

                    # Handle "uninterested" message
                    elif data["type"] == "uninterested":
                        self.download_queue.remove_interested_peer(peer_id)
                        self.download_queue.choke_peer(peer_id)
                        print(f"[INFO] Choking peer {addr}")

                    # Handle "request" message for a piece
                    elif data["type"] == "request":
                        index, begin, length = data["index"], data["begin"], data["length"]
                        if self.download_queue.add_request(peer_id, index, begin, length):
                            piece_data = self.piece_manager_seed.get_piece(index)
                            if piece_data:
                                piece_msg = self.message_factory.piece(index, begin, piece_data)
                                conn.sendall(piece_msg)
                                self.download_queue.mark_completed(peer_id, index, begin)
                                print(f"[INFO] Sent piece {index} to {addr}")

                    # Handle "piece" message
                    elif data["type"] == "piece":
                        index, begin, block = data["index"], data["begin"], data["block"]
                        self.piece_manager_seed.save_piece(index, block)
                        self.download_queue.mark_completed(peer_id, index, begin)
                        print(f"[INFO] Received block {begin} from {addr}")

                    # Handle "choke" message
                    elif data["type"] == "choke":
                        self.download_queue.choke_peer(peer_id)
                        print(f"[INFO] Peer {addr} choked us")

                    # Handle "unchoke" message
                    elif data["type"] == "unchoke":
                        self.download_queue.unchoked_peers.add(peer_id)
                        print(f"[INFO] Peer {addr} unchoked us")

                    # Handle "cancel" message
                    elif data["type"] == "cancel":
                        index, begin, length = data["index"], data["begin"], data["length"]
                        self.download_queue.cancel_request(peer_id, index, begin)
                        print(f"[INFO] Cancelled request for block {begin} from {addr}")

                    else:
                        print(f"[WARNING] Unknown message type from {addr}")

                except socket.timeout:
                    print(f"[WARNING] Timeout while waiting for data from {addr}")
                    break
                except ConnectionResetError:
                    print(f"[INFO] Connection reset by peer {addr}")
                    break
                except Exception as e:
                    print(f"[ERROR] Error with peer {addr}: {e}")
                    break

        finally:
            conn.close()
            self.download_queue.handle_disconnect(peer_id)
            print(f"[INFO] Connection with {addr} closed")



    def get_missing_pieces_from_peer(self, peer_bitfield):
        """
        Determine which pieces the peer has that we are missing.
        
        Args:
            peer_bitfield (list[int]): The bitfield of the peer.
        
        Returns:
            list[int]: List of piece indices that we are missing but the peer has.
        """
        missing_pieces = []
        for index, bit in enumerate(peer_bitfield):
            if bit == 1 and not self.piece_manager_seed.get_next_missing_piece(index):
                missing_pieces.append(index)
        return missing_pieces




    def get_piece(self, index):
        """Retrieve a piece by index for a specific file."""
        try:
            start = index * self.piece_length
            with open(self.shared_dir, "rb") as f:
                f.seek(start)
                data = f.read(self.piece_length)
            return data
        except Exception as e:
            print(f"[ERROR] Error reading piece {index} from {self.shared_dir}: {e}")
            return b""

    def download_piece(self, peer_ip, peer_port):
        """Download all pieces sequentially from a peer."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            try:
                client_socket.connect((peer_ip, peer_port))
                
                # Step 1: Send handshake
                handshake = self.message_factory.handshake(self.info_hash, self.peer_id.encode())
                client_socket.sendall(handshake)

                # Receive handshake response
                response = client_socket.recv(1024)
                data = self.message_parser.parse_message(response)
                if data["type"] != "handshake":
                    return

                bitfield_msg = self.message_factory.bitfield(self.piece_manager_leech.get_bitfield())
                client_socket.sendall(bitfield_msg)

                time.sleep(0.5)  # Sleep briefly to avoid busy-waiting
                # Step 2: Send INTERESTED message
                interested_msg = self.message_factory.interested()
                client_socket.sendall(interested_msg)
                 
                
                # Step 3: Wait for UNCHOKE response
                while True:
                    response = client_socket.recv(1024)
                    print("[DEBUG] Waiting for UNCHOKE message...")
                    data = self.message_parser.parse_message(response)
                    if data["type"] == "unchoke":
                        break
                    time.sleep(0.5)  # Sleep briefly to avoid busy-waiting

                # Step 4: Download all missing pieces
                while True:
                    print("[DEBUG] Requesting next missing piece...")
                    missing_piece = self.piece_manager_leech.get_next_missing_piece()
                    
                    # If no more missing pieces, break the loop
                    if missing_piece is None:
                        print("[INFO] All pieces have been downloaded.")
                        break

                    print(f"[DEBUG] Requesting piece {missing_piece} from {peer_ip}:{peer_port}")
                    
                    # Request the next missing piece
                    index, begin = missing_piece, 0
                    request_msg = self.message_factory.request(index, begin, 512 * 1024)
                    client_socket.sendall(request_msg)

                    # Step 5: Receive the requested piece
                    try:
                        response = client_socket.recv(1024 + 512 * 1024)
                        if not response:
                            print("[ERROR] No response received. Retrying...")
                            continue

                        piece_data = self.message_parser.parse_message(response)
                        if piece_data["type"] == "piece":
                            self.piece_manager_leech.save_piece(piece_data['index'], piece_data['block'])
                            self.download_queue.mark_completed(peer_ip, piece_data['index'], 0)
                            print(f"[INFO] Successfully downloaded piece {piece_data['index']}")

                    except socket.timeout:
                        print("[WARNING] Timeout while receiving piece. Retrying...")
                        continue

            except Exception as e:
                print(f"[ERROR] Error downloading from {peer_ip}:{peer_port}: {e}")
            finally:
                client_socket.close()




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
