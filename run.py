from lib import *
from utils import *
from torrent import Torrent
from peer import Peer


class Network:
    def __init__(self, peer_infos, tracker_info):
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

        self.num_peer = len(peer_infos)
        self.peer_infos = peer_infos
        self.tracker_info = tracker_info

        self.peers = []
        self.peer_servers = []
        self.connection_with_trackers = []

    def setup(self):
        shared_files_directory = r"TO_BE_SHARED"
        torrent_name = f"{shared_files_directory}.torrent"
        torrent_directory = "torrents"
        # Generate the torrent for the files in the 'files' subdirectory
        # generate_torrent(
        #     torrent_directory,
        #     shared_files_directory,
        #     self.tracker_info["url"],
        #     torrent_name,
        # )

        for peer_id, peer_info in self.peer_infos.items():
            torrent_path = os.path.join(torrent_directory, torrent_name)
            torrent = Torrent()
            torrent.load_torrent(torrent_path)

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
            with ThreadPoolExecutor(max_workers=40) as executor:
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


if __name__ == "__main__":
    # Number of peer in the network
    num_peer =2
    # The peer peer_info can be specified by users are generated automatically
    peer_infos = generate_peer_info(num_peer)
    tracker_info = generate_tracker_info()

    network = Network(peer_infos, tracker_info)
    print(network.num_peer)
    network.setup()
    network.run()
