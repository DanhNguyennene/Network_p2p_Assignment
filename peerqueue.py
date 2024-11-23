from threading import Lock


class DownloadQueue:
    def __init__(self, total_pieces, capacity=1):
        """
        Initialize the DownloadQueue with bitfield management and choking capacity.

        Args:
            total_pieces (int): Total number of pieces in the torrent.
            capacity (int): The maximum number of peers that can be unchoked simultaneously.
        """
        self.total_pieces = total_pieces
        self.capacity = capacity
        self.requests = {}  # {(index, begin): peer_id}
        self.peer_requests = {}  # {peer_id: [(index, begin)]}
        self.bitfield = {}  # Client's bitfield
        self.choked_peers = set()  # Set of choked peer_ids
        self.unchoked_peers = set()  # Set of unchoked peer_ids
        self.interested_peers = set()  # Set of interested peer_ids
        self.lock = Lock()

    def add_interested_peer(self, peer_id):
        """Mark a peer as interested."""
        with self.lock:
            self.interested_peers.add(peer_id)

    def remove_interested_peer(self, peer_id):
        """Remove a peer from the interested list."""
        with self.lock:
            self.interested_peers.discard(peer_id)

    def is_choked(self, peer_id):
        """Check if a peer is choked."""
        return peer_id in self.choked_peers

    def initialize_bitfield(self, peer_id, bitfield=None):
        """Initialize the bitfield for a peer."""
        if bitfield is None:
            bitfield = [0] * self.total_pieces
        self.bitfield[peer_id] = bitfield

    def add_request(self, peer_id, index, begin, length):
        """Add a block request to the queue if it's not already requested or completed."""
        with self.lock:
            key = (index, begin)

            if self.is_choked(peer_id):
                print(
                    f"[DEBUG] add_request() Peer {peer_id} is choked. Cannot add request."
                )
                return False

            if key in self.requests:
                print(
                    f"[DEBUG] Block {index} at begin {begin} is already requested or completed."
                )
                return False

            if self.bitfield[peer_id] and self.bitfield[peer_id][index] == 1:
                print(
                    f"[DEBUG] Peer {peer_id} already has block {index}. Not adding request."
                )
                return False

            # Add the request to the queue
            if peer_id not in self.peer_requests:
                self.peer_requests[peer_id] = []
                self.initialize_bitfield(peer_id)
            self.peer_requests[peer_id].append(key)

            return True

    def mark_completed(self, peer_id, index, begin):
        """Mark a block as completed and update the bitfield."""
        with self.lock:
            key = (index, begin)
            if key in self.requests and self.requests[key] == peer_id:
                del self.requests[key]
                if peer_id in self.peer_requests:
                    self.peer_requests[peer_id].remove(key)

                # Mark the piece as completed in the bitfield
                self.bitfield[peer_id][index] = 1
                print(f"[INFO] Block {key} marked as completed by peer {peer_id}")

    def choke_peer(self, peer_id):
        """Choke a peer."""
        with self.lock:
            self.choked_peers.add(peer_id)
            self.unchoked_peers.discard(peer_id)
            print(f"[INFO] Choked peer {peer_id}")

    def unchoke_peer(self, peer_id):
        """Unchoke a peer if within capacity."""
        with self.lock:
            if len(self.unchoked_peers) < self.capacity:
                self.choked_peers.discard(peer_id)
                self.unchoked_peers.add(peer_id)
                return True
            return False

    def cancel_request(self, peer_id, index, begin):
        """Cancel a block request."""
        with self.lock:
            key = (index, begin)
            if key in self.requests and self.requests[key] == peer_id:
                del self.requests[key]
                if peer_id in self.peer_requests:
                    self.peer_requests[peer_id].remove(key)
                print(f"[INFO] Cancelled request for block {key} from peer {peer_id}")

    def update_bitfield(self, peer_id, bitfield):
        """Update the bitfield for a peer."""
        with self.lock:
            self.bitfield[peer_id] = bitfield

    def get_next_request(self):
        """Get the next missing piece to request."""
        with self.lock:
            for index, bit in enumerate(self.bitfield):
                if bit == 0:  # If the piece is missing
                    return index
            return None

    def handle_disconnect(self, peer_id):
        """Handle a peer disconnection."""
        with self.lock:
            if peer_id in self.peer_requests:
                for key in self.peer_requests[peer_id]:
                    if key in self.requests:
                        del self.requests[key]
                del self.peer_requests[peer_id]
                self.choked_peers.discard(peer_id)
                self.unchoked_peers.discard(peer_id)
                self.interested_peers.discard(peer_id)

    def manage_unchoking(self):
        """Dynamically unchoke interested peers based on capacity."""
        with self.lock:
            for peer_id in self.interested_peers:
                if peer_id not in self.unchoked_peers:
                    if self.unchoke_peer(peer_id):
                        print(f"[INFO] Unchoked interested peer {peer_id}")

            # Choke excess peers if we are over capacity
            if len(self.unchoked_peers) > self.capacity:
                extra_peers = list(self.unchoked_peers)[self.capacity :]
                for peer_id in extra_peers:
                    self.choke_peer(peer_id)
                    print(f"[INFO] Choked peer {peer_id} due to capacity limit")
