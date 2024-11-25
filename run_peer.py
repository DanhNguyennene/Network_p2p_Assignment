from lib import *
from utils import *
from torrent import Torrent
from peer import Peer


class RunPeer:
    def __init__(self):
        """
        peer_info:
        {
            "address": (peer_ip, peer_port),
            "torrent_name": "torrent_X.torrent",
            "directory": "./X/",
            "files_directory": "./X/files",
        }

        tracker_info:
        {
            "url": "http://127.0.0.1:8000/"
        }
        """
        self.peer_info = None
        self.tracker_info = None
        self.peer = None

    def setup(self):
        shared_files_directory = r"TO_BE_SHARED"
        torrent_name = f"{shared_files_directory}.torrent"
        torrent_directory = "torrents"

        torrent_path = os.path.join(torrent_directory, torrent_name)
        torrent = Torrent()
        torrent.load_torrent(torrent_path)

        id = input("Enter a peer id (ex: A1, A2, B1, B3): ")

        self.peer_info = generate_peer_info(id, 6881 + int(id[-1]))
        self.tracker_info = generate_tracker_info()

        peer_id = self.peer_info["id"]
        peer_ip, peer_port = self.peer_info["address"]
        peer_directory = self.peer_info["directory"]

        # Ensure the peer's directory and the files subdirectory exist
        os.makedirs(peer_directory, exist_ok=True)

        # Create the peer
        self.peer = Peer(
            torrent,
            peer_id,
            peer_ip,
            peer_port,
            peer_directory,
        )

        # Register peer with tracker
        register_thread = threading.Thread(target=self.peer.register_with_tracker)
        register_thread.daemon = True
        register_thread.start()

        # Start the peer server
        server_thread = threading.Thread(target=self.peer.start_server)
        server_thread.daemon = True
        server_thread.start()

        # Ensure sufficient time for the server to initialize
        time.sleep(2)

    # def health(self):
    #     """Check the health of the torrent by displaying scrape information from the tracker."""
    #     scrape_info = self.peer.get_tracker_scrape_info()
    #     print("Tracker Scrape Info:")
    #     for file_info in scrape_info:
    #         print(file_info)

    def start(self):
        """Start downloading all files specified in the torrent."""
        start_thread = threading.Thread(target=self.peer.start_clients)
        start_thread.daemon = True
        start_thread.start()

    # def neighbours(self):
    #     """Get the list of connecting peers."""
    #     neighbors = self.peer.get_neighbors()
    #     print("Connected Peers:")
    #     for neighbor in neighbors:
    #         print(neighbor)

    def shutdown(self):
        """Stop downloading."""
        self.peer.shutdown()

    # def continue_downloading(self):
    #     """Continue downloading."""
    #     self.peer.resume_downloading()
    #     print("Downloading continued.")

    def run_cli(self):
        """Run the CLI interface for the peer."""
        while True:
            command = input(f"Peer {self.peer_info["id"]}> ").strip().lower()
            if command == "health":
                print("[INFO] Haven't implement yet")
                # self.health()
            elif command == "start":
                self.start()
            elif command == "neighbours":
                print("[INFO] Haven't implement yet")
                # self.neighbours()
            elif command in {"exit", "quit", "shutdown"}:
                print("Shutting down peer...")
                self.peer.shutdown()
                break
            else:
                print(
                    "Unknown command. Available commands: health, start, neighbours, stop, continue, exit"
                )


if __name__ == "__main__":
    peer_cli = RunPeer()
    peer_cli.setup()
    peer_cli.run_cli()
