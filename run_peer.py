from lib import *
from utils import *
from peer import PeerNode
from torrent import Torrent


def run_seeders_and_leechers(num_seeders=1, num_leechers=1):
    generate_torrent("shared", "/", "torrents")
    peers = []
    seeder_ports = [6881]
    leecher_ports = [6882, 6883, 6884]

    torrent = Torrent()
    torrent.load_torrent(r"torrents\shared.torrent")

    # Initialize and start seeders
    for i in range(num_seeders):
        seeder_id = f"seeder00{i+1}"
        seeder_ip = "127.0.0.1"
        seeder_port = seeder_ports[i]
        seeder = PeerNode(torrent, seeder_id, seeder_ip, seeder_port, is_seeder=True)
        seeder.register_with_tracker()
        seeder.get_peers()
        peers.append(seeder)

        # Start the seeder server in a separate thread
        server_thread = threading.Thread(target=seeder.start_server)
        server_thread.daemon = True
        server_thread.start()
        print(f"{seeder_id} is running on port {seeder_port} and sharing {shared_file}")

    # Initialize and start leechers
    for i in range(num_leechers):
        leecher_id = f"leecher00{i+1}"
        leecher_ip = "127.0.0.1"
        leecher_port = leecher_ports[i]
        leecher = PeerNode(
            shared_file, leecher_id, leecher_ip, leecher_port, is_seeder=False
        )
        leecher.register_with_tracker()
        peers.append(leecher)

        # Start the leecher server in a separate thread
        server_thread = threading.Thread(target=leecher.start_server)
        server_thread.daemon = True
        server_thread.start()
        print(
            f"{leecher_id} is running on port {leecher_port} and downloading {shared_file}"
        )

    # Give some time for peers to start up
    time.sleep(2)

    # Leechers start downloading from seeders
    for leecher in [p for p in peers if not p.is_seeder]:
        for file_info in leecher.files:
            file_path = file_info["path"]
            print(file_path)
            for i in range(file_info["num_pieces"]):
                if not leecher.pieces_downloaded[file_path][i]:
                    for seeder in [p for p in peers if p.is_seeder]:
                        try:
                            leecher.download_piece(file_path, i, seeder.ip, seeder.port)
                        except Exception as e:
                            print(
                                f"Error downloading piece {i} of {file_path} from {seeder.peer_id}: {e}"
                            )
                        break

    print("Press Ctrl+C to stop all peers...")

    try:
        # Keep the script running to allow peers to communicate
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down all peers...")
        for peer in peers:
            peer.shutdown()


if __name__ == "__main__":
    run_seeders_and_leechers()
