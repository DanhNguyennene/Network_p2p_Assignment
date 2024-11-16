from threading import Lock

class DownloadQueue:
    def __init__(self, total_pieces, capacity=40):
        """
        Initialize the DownloadQueue with bitfield management and choking capacity.
        Args:
            total_pieces (int): Total number of pieces in the torrent.
            capacity (int): The maximum number of outstanding requests per peer.
        """
        self.total_pieces = total_pieces
        self.capacity = capacity
        self.requests = {}  # Format: {(index, begin): peer_id}
        self.completed_blocks = set()
        self.peer_requests = {}  # {peer_id: list of (index, begin)}
        self.choked_peers = set()
        self.bitfield = [0] * total_pieces
        self.lock = Lock()

    def add_request(self, peer_id, index, begin, length):
        """Add a block request to the queue if the piece is missing."""
        with self.lock:
            if self.is_choked(peer_id):
                return False

            key = (index, begin)
            if self.bitfield[index] == 1 or key in self.requests or key in self.completed_blocks:
                return False

            self.requests[key] = peer_id
            if peer_id not in self.peer_requests:
                self.peer_requests[peer_id] = []
            self.peer_requests[peer_id].append(key)

            # Choke the peer if it exceeds the capacity
            if len(self.peer_requests[peer_id]) > self.capacity:
                self.choked_peers.add(peer_id)
                print(f"[INFO] Choked peer {peer_id} due to capacity limit")

            return True

    def mark_completed(self, peer_id, index, begin):
        """Mark a block as completed and update the bitfield."""
        with self.lock:
            key = (index, begin)
            if key in self.requests and self.requests[key] == peer_id:
                del self.requests[key]
                self.completed_blocks.add(key)
                self.bitfield[index] = 1
                if peer_id in self.peer_requests:
                    self.peer_requests[peer_id].remove(key)
                    if len(self.peer_requests[peer_id]) <= self.capacity:
                        self.choked_peers.discard(peer_id)

    def is_choked(self, peer_id):
        """Check if a peer is currently choked."""
        return peer_id in self.choked_peers

    def handle_disconnect(self, peer_id):
        """Handle recovery when a peer disconnects."""
        with self.lock:
            reassigned_blocks = []
            if peer_id in self.peer_requests:
                for key in self.peer_requests[peer_id]:
                    del self.requests[key]
                    reassigned_blocks.append(key)
                del self.peer_requests[peer_id]
                self.choked_peers.discard(peer_id)
            return reassigned_blocks
