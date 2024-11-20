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
        self.peer_threads = []

    def setup(self):
        for peer_id, peer_info in self.peer_infos.items():

            # Ensure the peer's directory and the files subdirectory exist
            os.makedirs(peer_info["files_directory"], exist_ok=True)

            # Generate the torrent for the files in the 'files' subdirectory
            generate_torrent(
                peer_info["directory"],
                peer_info["files_directory"],
                self.tracker_info["url"],
                peer_info["torrent_name"],
            )

            peer_ip, peer_port = peer_info["address"]
            peer_directory = peer_info["directory"]
            peer_torrent_name = peer_info["torrent_name"]

            torrent_path = os.path.join(peer_directory, peer_torrent_name)
            torrent = Torrent()
            torrent.load_torrent(torrent_path)

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

            print(
                f"[DEBUG] Peer {peer.ip} is connecting with Tracker {self.tracker_info["url"]}"
            )

        for peer in self.peers:
            server_thread = threading.Thread(target=peer.start_server)
            server_thread.daemon = True
            server_thread.start()

            print(f"[DEBUG] Peer {peer.ip} is running on port {peer.port}")

            self.peer_threads.append(server_thread)

    def run(self):
        def download_from_seeder(peer):
            peer.download_piece()

        # Assuming you have a list of peers and a seeder
        with ThreadPoolExecutor() as executor:
            # Iterate through all leechers and submit their download tasks to the executor
            futures = [
                executor.submit(download_from_seeder, peer)
                for peer in [p for p in self.peers]
            ]

            # Optionally, wait for all downloads to complete
            for future in futures.as_completed(futures):
                try:
                    future.result()  # You can check for exceptions here
                except Exception as e:
                    print(f"Error downloading piece: {e}")

        print("Press Ctrl+C to stop all peers...")


if __name__ == "__main__":
    # Number of peer in the network
    num_peer = 3
    # The peer peer_info can be specified by users are generated automatically
    peer_infos = generate_peer_info(num_peer)
    tracker_info = generate_tracker_info()

    network = Network(peer_infos, tracker_info)
    network.setup()
    network.run()
