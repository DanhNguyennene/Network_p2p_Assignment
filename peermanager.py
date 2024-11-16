from lib import *
from peer import Peer


class PeerManager(threading.Thread):
    def __init__(self, torrent, peer_id, max_peers=5):
        super().__init__()
        self.torrent = torrent  # Torrent metadata (info, piece length, etc.)
        self.peer_id = peer_id  # Unique identifier for this client
        self.peers = []  # List to hold PeerNode instances
        self.max_peers = max_peers  # Max number of simultaneous peer connections
        self.shutdown_event = threading.Event()

    def run(self):
        pass
