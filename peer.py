from lib import *
from torrent import *
from message import *
from peerqueue import DownloadQueue
from piecemanager import PieceManager


class Peer:
    def __init__(
        self,
        torrent,
        id,
        ip,
        port,
        dir,
    ):
        self.id = id
        self.ip = ip
        self.port = port
        self.is_seeder = False
        self.server_socket = None

        self.downloaded = 0
        self.uploaded = 0

        self.available_peers = []
        self.interval = 0

        self.dir = dir
        print("INITIALIZING PIECE MANAGER FOR PEER")
        self.piece_manager = PieceManager(torrent, dir)
        print(f"[DEBUG] {self.id} bitfield: {self.piece_manager.get_bitfield()}")
        self.download_queue = DownloadQueue(self.piece_manager.get_total_pieces())

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

        self._update_is_seeder()

    # def _update_is_seeder(self):
    #     self.is_seeder

    def _update_is_seeder(self):
        bitfield = self.piece_manager.get_bitfield()
        for i in range(len(bitfield)):
            if bitfield[i] == 0:
                self.is_seeder = False
                return
        self.is_seeder = True

    def register_with_tracker(self):
        try:
            while not self.shutdown_event.is_set():
                """Register with the tracker and get a list of peers."""
                data = {
                    "info_hash": self.info_hash.hex(),
                    "peer_id": self.id,
                    "ip": self.ip,
                    "port": self.port,
                    "downloaded": self.downloaded,
                    "uploaded": self.uploaded,
                    "is_seeder": self.is_seeder,
                }

                print(
                    f"[DEBUG] register_with_tracker() {self.id} Registering with tracker: {self.tracker_url + "announce"}"
                )
                response = requests.get(self.tracker_url + "announce", json=data)

                # Parse the reponse received from tracker
                if response.status_code == 200:
                    peer_data = response.json()

                    self.available_peers = peer_data.get("peers", [])
                    self.interval = peer_data.get("interval", 0)
                    # print(
                    #     f"[DEBUG] register_with_tracker() {self.id} Updated available peers: {[(available_peer["peer_id"], available_peer["port"], available_peer["is_seeder"]) for available_peer in self.available_peers]}"
                    # )
                else:
                    print(
                        f"[ERROR] {self.id} register_with_tracker() Failed to fetch peers. Status code: {response.status_code}"
                    )

                # Sleep for interval
                time.sleep(self.interval)
        except requests.RequestException as e:
            print(f"[ERROR] registering with tracker: {e}")

    # def get_peers(self):
    #     """Get the list of peers from the tracker"""
    #     data = {
    #         "info_hash": self.info_hash,
    #     }
    #     try:
    #         response = requests.get(self.tracker_url + "get_peers", json=data)
    #         return response.json()
    #     except request.RequestException as e:
    #         print(f"[ERROR] fetching data from tracker: {e}")

    def start_server(self,timeout=100000):
        """Start the peer server to handle piece requests."""

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.ip, self.port))
            self.server_socket.listen()
            self.server_socket.settimeout(timeout)
            print(
                f"[DEBUG] start_server() {self.id} listening on {self.ip}:{self.port}"
            )

            while not self.shutdown_event.is_set():
                try:
                    conn, addr = self.server_socket.accept()
                    print(
                        f"[DEBUG] start_server() {self.id} received {addr}", addr
                    )  # block until receive a request
                    self.executor.submit(
                        self.handle_client, conn, addr
                    )  # threading running the handle_client function
                except socket.timeout:
                    print(f"[DEBUG] start_server() {self.id} Timeout while waiting for connection")
        except Exception as e:
            print(f"Error in server: {e}")
        finally:
            self.server_socket.close()


    def start_clients(self):
        """Start client threads to connect to available peers and download pieces."""

        try:
            print(
                f"[DEBUG] start_clients() {self.id} Starting client threads for P2P connections..."
            )

            # Set to track already connected peers
            connected_peers = set()

            while not self.shutdown_event.is_set():

                if not self.available_peers:
                    print(
                        f"[DEBUG] start_clients() {self.id} No available peers. Waiting for updates..."
                    )
                    time.sleep(self.interval)  # Wait for registering with tracker
                    continue
                
                # Iterate over the list of available peers
                for peer in self.available_peers:
                
                    peer_ip = peer.get("ip")
                    peer_port = peer.get("port")
                    peer_key = (peer_ip, peer_port)

                    if peer_key in connected_peers:
                        # Skip already connected peers
                        continue

                    if peer_ip == self.ip and peer_port == self.port:
                        # Skip connecting to itself
                        continue

                    # Mark the peer as connected
                    connected_peers.add(peer_key)
                    if self.is_seeder:
                        continue    
                    # Start a thread to handle the connection and download
                    self.executor.submit(self._connect_and_download, peer_ip, peer_port)

                # Sleep briefly to avoid busy-looping
                time.sleep(self.interval)

        except Exception as e:
            print(f"[ERROR] start_clients() {self.id} Error in start_clients: {e}")
        finally:
            print(f"[INFO] start_clients() {self.id} Shutting down client threads...")


    def handle_client(self, conn, addr):
        peer_id = addr
        print(f"[DEBUG] handle_client() {self.id} Accept connection from {addr}")

        try:

            ###########################
            ##                       ##
            ##   STEP 1: HANDSHAKE   ##
            ##                       ##
            ###########################

            # Receive client handshake
            request = conn.recv(1024)
            data = self.message_parser.parse_message(request)
            if data is None or data["type"] != "handshake":
                print(f"[ERROR] Invalid handshake from {addr}")
                return

            # Send server handshake
            response = self.message_factory.handshake(self.info_hash, self.id.encode())
            conn.sendall(response)

            ##########################
            ##                      ##
            ##   STEP 2: HANDLE     ##
            ##                      ##
            ##########################

            peer_bitfield = None

            while True:
                try:
                    request = conn.recv(1024)

                    # Handle connection closure
                    if not request:
                        print(f"[INFO] Connection closed by peer {addr}")
                        break

                    # Parse message
                    data = self.message_parser.parse_message(request)

                    # Handle error message
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
                        print(
                            f"[DEBUG] handle_client() {self.id} Received bitfield from {addr}"
                        )
                        print(f"[DEBUG] handle_client() {self.id} bitfield: {peer_bitfield}")
                        self.download_queue.update_bitfield(peer_id, peer_bitfield)
                        continue

                    # Handle "interested" message
                    if data["type"] == "interested":
                        self.download_queue.add_interested_peer(peer_id)
                        if self.download_queue.unchoke_peer(peer_id):
                            print(
                                f"[DEBUG] handle_client() {self.id} Unchoked peer at {addr}"
                            )
                            unchoke_msg = self.message_factory.unchoke()
                            conn.sendall(unchoke_msg)
                        else:
                            print(
                                f"[DEBUG] handle_client() {self.id} Can't Unchoked peer at {addr}"
                            )
                            deny_msg = self.message_factory.deny_unchoke()
                            conn.sendall(deny_msg)
                            continue
                        

                    # Handle "uninterested" message
                    elif data["type"] == "uninterested":
                        self.download_queue.remove_interested_peer(peer_id)
                        self.download_queue.choke_peer(peer_id)
                        print(f"[INFO] Choking peer {addr}")

                    # Handle "request" message for a piece
                    elif data["type"] == "request":
                        index, begin, length = (
                            data["index"],
                            data["begin"],
                            data["length"],
                        )
                        if self.download_queue.capacity < len(self.download_queue.unchoked_peers):

                            deny_msg = self.message_factory.deny_unchoke()
                            conn.sendall(deny_msg)
                            print(f"[INFO] Peer {addr} is denied")
                            continue
                        if self.download_queue.add_request(
                            peer_id, index, begin, length
                        ):
                            print(
                                f"[DEBUG] handle_client() {self.id} added request for block {index} from peer {peer_id}"
                            )
                            piece_data = self.piece_manager.get_piece(index)

                            if piece_data:
                                piece_msg = self.message_factory.piece(
                                    index, begin, piece_data
                                )
                                conn.sendall(piece_msg)
                                self.download_queue.mark_completed(
                                    peer_id, index, begin
                                )
                                print(
                                    f"[DEBUG] handle_client() {self.id} sent piece {index} to {addr}"
                                )
                            else:
                                print(
                                    f"[DEBUG] handle_client() {self.id} piece {index} not found"
                                )
                                piece_msg = self.message_factory.dont_have_piece()
                                conn.sendall(piece_msg)

                                # tạo ra một cái protocal nữa ở messgae thông báo là không có piêc đó để leecher nó hỏi piece kahcs


                    # Handle "piece" message
                    elif data["type"] == "piece":
                        index, begin, block = (
                            data["index"],
                            data["begin"],
                            data["block"],
                        )
                        self.piece_manager.save_piece(index, block)
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
                        index, begin, length = (
                            data["index"],
                            data["begin"],
                            data["length"],
                        )
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
            time.sleep(1)
            print(f"[DEBUG] handle_client {self.id} close connection with {addr}")

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

    def _connect_and_download(self, peer_ip, peer_port):
        """Handle the connection and download process for a single peer."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.connect((peer_ip, peer_port))
                print(
                    f"[DEBUG] _connect_and_download() {self.id} Connected to peer at {peer_ip}:{peer_port}"
                )
                if self.is_seeder:
                    print(
                        f"[DEBUG] _connect_and_download() {self.id} Peer {peer_ip}:{peer_port} is a seeder"
                    )
                    return
                # Perform the download process

                self.download_piece(client_socket, peer_ip, peer_port)

        except Exception as e:
            print(f"[ERROR] Failed to connect to peer {peer_ip}:{peer_port}: {e}")

    def download_piece(self, client_socket, peer_ip, peer_port,unchoke_retry=5):
        """Download all pieces sequentially from a peer."""
        try:

            ###########################
            ##                       ##
            ##   STEP 1: HANDSHAKE   ##
            ##                       ##
            ###########################

            # Send client handshake
            handshake = self.message_factory.handshake(self.info_hash, self.id.encode())
            client_socket.sendall(handshake)

            # Receive server handshake
            response = client_socket.recv(1024)
            data = self.message_parser.parse_message(response)
            if data["type"] != "handshake":
                return
            print(
                f"[DEBUG] download_piece() {self.id} Handshake with ({peer_ip, peer_port}) completed"
            )

            ###########################
            ##                       ##
            ##   STEP 2: BITFIELD    ##
            ##                       ##
            ###########################

            # Send client bitfield
            bitfield_msg = self.message_factory.bitfield(
                self.piece_manager.get_bitfield()
            )
            client_socket.sendall(bitfield_msg)

            time.sleep(0.5)  # Sleep briefly to avoid busy-waiting

            ############################
            ##                        ##
            ##   STEP 3: INTERESTED   ##
            ##                        ##
            ############################



            # Recieve server unchoke
            while True:  # (maybe unnecessary)
                # Send client interested
                if unchoke_retry <= 0:
                    print(
                        f"[DEBUG] download_piece() {self.id} Unchoke denied from ({peer_ip, peer_port})"
                    )
                    break
                interested_msg = self.message_factory.interested()
                client_socket.sendall(interested_msg)
                print(
                    f"[DEBUG] download_piece() {self.id} Waiting for unchoke from ({peer_ip, peer_port})"
                )
                response = client_socket.recv(1024)
                data = self.message_parser.parse_message(response)
                if data["type"] == "unchoke":
                    break
                elif data["type"] == "deny_unchoke":
                    unchoke_retry -=1
                    print(
                        f"[DEBUG] download_piece() {self.id} Waiting for unchoke from ({peer_ip, peer_port}), Retry in 5 seconds"
                    )
                    time.sleep(5)

                time.sleep(0.5)  # Sleep briefly to avoid busy-waiting

            ##########################
            ##                      ##
            ##   STEP 4: DOWNLOAD   ##
            ##                      ##
            ##########################
            missing_index = 0
            while True:

                missing_piece = self.piece_manager.get_next_missing_piece()

                # If no more missing pieces, break the loop
                if missing_piece is None:
                    print("[INFO] All pieces have been downloaded.")
                    break
                if missing_index >= len(missing_piece):
                    break
                print(
                    f"[DEBUG] download_piece() {self.id} requesting piece {missing_piece[0]} from ({peer_ip},{peer_port})"
                )

                # Request the next missing piece
                index, begin = missing_piece[missing_index], 0
                request_msg = self.message_factory.request(index, begin, 512 * 1024)
                client_socket.sendall(request_msg)

                # Step 5: Receive the requested piece
                try:
                    def recv_all(sock, length):
                        """Utility function to receive a specific number of bytes from the socket."""
                        data = b""
                        while len(data) < length:
                            usual_len = len(data)
                            packet = sock.recv(length - len(data))
                            if not packet:
                                return None  # Connection closed unexpectedly
                            data += packet
                        usual_len = len(data)
                        print(usual_len)
                        return data

                    # Usage:
                    expected_length = 13 + self.piece_manager.get_piece_length(index)
                    response = recv_all(client_socket, expected_length)

                    if not response:
                        print("[ERROR] No response received. Retrying...")
                        continue

                    piece_data = self.message_parser.parse_message(response)
                    if piece_data["type"] == "piece":
                        print("Saving piece")
                        self.piece_manager.save_piece(
                            piece_data["index"], piece_data["block"]
                        )
                        self.piece_manager.mark_piece_completed(piece_data["index"])
                        print(
                            f"[INFO] Successfully downloaded piece {piece_data['index']}"
                        )
                    elif piece_data["type"] == "dont_have_piece":
                        print(
                            f"[INFO] Peer {peer_ip} does not have the requested piece"
                        )
                        missing_index+=1
                        missing_piece = missing_piece[missing_index:]

                except socket.timeout:
                    print("[WARNING] Timeout while receiving piece. Retrying...")
                    continue

        except Exception as e:
            print(f"[ERROR] Error downloading from {peer_ip}:{peer_port}: {e}")
        finally:
            self._update_is_seeder()
            client_socket.close()
            time.sleep(1)


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
