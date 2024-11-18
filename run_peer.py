from lib import *
from utils import *
from peer import Peer
from torrent import Torrent

TRACKER_URL ="http://127.0.0.1:8000/"

def run_seeders_and_leechers(num_seeders=1, num_leechers=2):

    os.makedirs("downloads", exist_ok=True)
    os.makedirs(os.path.join("TO_BE_SHARED","shared"), exist_ok=True)
    generate_torrent(os.path.join("TO_BE_SHARED","shared"), TRACKER_URL, "torrents")
    peers = []
    seeder_ports = [6881]
    leecher_ports = [6882, 6883, 6884]

    torrent = Torrent()
    torrent.load_torrent(r"torrents\shared.torrent")

    # Initialize and start seeders
    for i in range(num_seeders):
        seeder_id = f"A{i+1}"
        seeder_ip = "127.0.0.1"
        seeder_port = seeder_ports[i]
        seeder = Peer(torrent, seeder_id, seeder_ip, seeder_port, is_seeder=True,shared_dir="TO_BE_SHARED")
        seeder.register_with_tracker()
        peers.append(seeder)

        # Start the seeder server in a separate thread
        server_thread = threading.Thread(target=seeder.start_server)
        server_thread.daemon = True
        server_thread.start()
        print(f"{seeder_id} is running on port {seeder_port} and sharing ")

    # Initialize and start leechers
    for i in range(num_leechers):
        leecher_id = f"A{i+1}"
        leecher_ip = "127.0.0.1"
        leecher_port = leecher_ports[i]
        leecher = Peer(
            torrent, leecher_id, leecher_ip, leecher_port, is_seeder=False,downloaded_dir=f"downloads_{leecher_port}"
        )
        leecher.register_with_tracker()
        peers.append(leecher)

        # Start the leecher server in a separate thread
        server_thread = threading.Thread(target=leecher.start_server)
        server_thread.daemon = True
        server_thread.start()
        print(f"{leecher_id} is running on port {leecher_port} and downloading ")

    # Give some time for peers to start up
    time.sleep(2)

    def download_from_seeder(leecher, seeder_ip, seeder_port):
        leecher.download_piece(seeder_ip, seeder_port)

    # Assuming you have a list of peers and a seeder
    with ThreadPoolExecutor() as executor:
        # Iterate through all leechers and submit their download tasks to the executor
        futures = [
            executor.submit(download_from_seeder, leecher, seeder.ip, seeder.port)
            for leecher in [p for p in peers if not p.is_seeder]
        ]

        # Optionally, wait for all downloads to complete
        for future in futures.as_completed(futures):
            try:
                future.result()  # You can check for exceptions here
            except Exception as e:
                print(f"Error downloading piece: {e}")

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
