from lib import *
from utils import *
from torrent import Torrent
from peer import Peer

class Network:
    def __init__(self):
        """
        peer_info:
        {
            "A0": {
                address: (peer_ip, peer_port)
                torrent_name: "torrent_A0.torrent",
                directory: "./A0/"
                files_directory: "./A0/files"
            },
            "A1": {...},
            "A2": {...},
        }

        tracker_info:
        {
            "url": "http://127.0.0.1:8000/"
        }
        """

        self.num_peer = 0

        self.peer_infos = {}
        # self.tracker_info = tracker_info

        self.peers = []
        self.peer_servers = []
        self.connection_with_trackers = []
        self.shared_files_directory = []
        self.torrent_taken = set()
        self.peer_port = []
        self.peer_to_run = {}

    def update_torrent_and_run(self,torrent_paths,no_run_thread=False):
        self.shared_files_directory = [torrent_path for torrent_path in torrent_paths if torrent_path not in self.torrent_taken]
        self.torrent_taken.update(self.shared_files_directory)
        self.peer_to_run = {}
        self.num_peer = len(torrent_paths)
        for i in range(self.num_peer):
            self.peer_port.append(self.peer_port[-1] + +1) if self.peer_port else self.peer_port.append(6881)
            peer_info, peer_id = generate_peer_info(i,self.peer_port[-1])
            self.peer_infos[peer_id] = peer_info
            self.peer_to_run[peer_id] = peer_info
        self.setup()
        if not no_run_thread:
            threading.Thread(target=self.run, daemon=True).start()
        else:
            self.run()
        
    def setup(self):
        # shared_files_directory = r"TO_BE_SHARED"
        # torrent_name = f"{shared_files_directory}.torrent"
        # torrent_directory = "torrents"
        # Generate the torrent for the files in the 'files' subdirectory
        # generate_torrent(
        #     torrent_directory,
        #     shared_files_directory,
        #     self.tracker_info["url"],
        #     torrent_name,
        # )

        for torrent_index,(peer_id, peer_info) in enumerate(self.peer_to_run.items()):

            # torrent_path = os.path.join(torrent_directory, torrent_name)

            torrent = Torrent()

            torrent.load_torrent(self.shared_files_directory[torrent_index])

            peer_ip, peer_port = peer_info["address"]
            peer_directory = peer_info["directory"]

            # Ensure the peer's directory and the files subdirectory exist
            os.makedirs(peer_directory, exist_ok=True)

            # Create the peer
            peer = Peer(
                torrent,
                peer_id,
                peer_ip,
                peer_port,
                peer_directory,
            )

            self.peers.append(peer)

        for peer in self.peers:
            connection_with_tracker_thread = threading.Thread(
                target=peer.register_with_tracker
            )
            connection_with_tracker_thread.daemon = True
            connection_with_tracker_thread.start()

            self.connection_with_trackers.append(connection_with_tracker_thread)

        for peer in self.peers:
            peer_server_thread = threading.Thread(target=peer.start_server)
            peer_server_thread.daemon = True
            peer_server_thread.start()

            self.peer_servers.append(peer_server_thread)

    def run(self):
        def start_p2p_connections(peer):
            peer.start_clients()
        # IMPORTANT: Wait for all peers to register with the tracker before starting P2P connections at least 5 seconds
        time.sleep(5)
        print('self.peers:',self.peers)
        try:
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(start_p2p_connections, peer) for peer in self.peers
                ]

                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        print(f"Error in P2P connections: {e}")

            print("Press Ctrl+C to stop all peers...")

        except KeyboardInterrupt:
            print("\nShutting down...")

        finally:
            self.shutdown()

    def shutdown(self):
        for peer in self.peers:
            try:
                peer.shutdown()  # Assuming Peer has a method to stop server
            except Exception as e:
                print(f"Error stopping peer server: {e}")

        for thread in self.peer_servers:
            if thread.is_alive():
                thread.join(timeout=1)

        for thread in self.connection_with_trackers:
            if thread.is_alive():
                thread.join(timeout=1)
