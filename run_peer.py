from lib import *
from peer import PeerNode
import threading
import time

def run_multiple_peers(num_peers=3):
    peers = []
    ports = [6881, 6882, 6883]  # Example ports for multiple peers
    shared_files = ["shared/file1.dat", "shared/file2.dat", "shared/file3.dat"]

    # Initialize and start multiple peers
    for i in range(num_peers):
        peer_id = f"peer00{i+1}"
        ip = "127.0.0.1"
        port = ports[i]
        file_path = shared_files[i]

        # Create a PeerNode instance
        peer = PeerNode(peer_id, ip, port, file_path)
        peer.register_with_tracker()
        peers.append(peer)

        # Start the peer server in a separate thread
        server_thread = threading.Thread(target=peer.start_server)
        server_thread.daemon = True
        server_thread.start()

        print(f"{peer_id} is running on port {port} and sharing {file_path}")

    # Give some time for peers to start up
    time.sleep(2)

    # Example: Each peer tries to download a piece from another peer
    for i, peer in enumerate(peers):
        target_peer_index = (i + 1) % num_peers  # Download from the next peer
        target_ip = "127.0.0.1"
        target_port = ports[target_peer_index]
        print(f"{peer.peer_id} trying to download piece 0 from {target_ip}:{target_port}")
        peer.download_piece(0, target_ip, target_port)

    print("Press Ctrl+C to stop all peers...")

    try:
        # Keep the script running to allow peers to communicate
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down all peers...")
        for peer in peers:
            peer.shutdown()

if __name__ == '__main__':
    run_multiple_peers()
