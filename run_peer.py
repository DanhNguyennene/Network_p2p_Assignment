from lib import *
from peer import PeerNode
def signal_handler(signal, frame, shutdown_event):
    print("\nShutting down peer...")
    shutdown_event.set()

def run_peer():
    peer_id = "peer001"
    ip = "127.0.0.1"
    port = 6881
    shared_files = {
        "file1_hash": "shared/file1.dat",
        "file2_hash": "shared/file2.dat"
    }

    peer = PeerNode(peer_id, ip, port, shared_files)
    peer.register_with_tracker()

    # Start peer server in a separate thread
    server_thread = threading.Thread(target=peer.start_server)
    server_thread.start()

    # Use an Event to block the main thread and keep the server running
    shutdown_event = threading.Event()

    # Register the signal handler for Ctrl+C
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, shutdown_event))

    try:
        peer.download_file("file1_hash")
        print("Press Ctrl+C to stop the server...")
        shutdown_event.wait()  # Block here until the shutdown event is set
    finally:
        peer.shutdown()
        server_thread.join()

if __name__ == '__main__':
    run_peer()