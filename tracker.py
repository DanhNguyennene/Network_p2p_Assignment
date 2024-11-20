from lib import *


class Tracker:
    def __init__(self, tracker_id: str, ip: str, port: int):
        """Initialize the tracker with basic configuration.

        Args:
            tracker_id: Unique identifier for this tracker
            ip: IP address to bind to
            port: Port number to listen on
        """
        self.tracker_id = tracker_id
        self.ip = ip
        self.port = port
        self.peers: Dict[str, Dict] = {}  # info_hash -> peer_dict
        self.last_cleanup = datetime.now()

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

    def _validate_peer_data(self, data: dict) -> bool:
        """Validate incoming peer data has all required fields.

        Args:
            data: Dictionary containing peer information

        Returns:
            bool: True if valid, False otherwise
        """
        required_fields = ["peer_id", "ip", "port", "info_hash"]
        return all(field in data for field in required_fields)

    def _cleanup_inactive_peers(self, max_age_minutes: int = 30) -> None:
        """Remove peers that haven't announced in the specified time period."""
        current_time = datetime.now()
        if (
            current_time - self.last_cleanup
        ).total_seconds() < 300:  # Run every 5 minutes
            return

        for info_hash in list(self.peers.keys()):
            for peer_id in list(self.peers[info_hash].keys()):
                last_seen = self.peers[info_hash][peer_id].get("last_seen")
                if last_seen and (current_time - last_seen).total_seconds() > (
                    max_age_minutes * 60
                ):
                    del self.peers[info_hash][peer_id]

            # Remove empty info_hashes
            if not self.peers[info_hash]:
                del self.peers[info_hash]

        self.last_cleanup = current_time

    def _update_peers(self, data: dict) -> bool:
        """Update peer information in the tracker.

        Args:
            data: Dictionary containing peer information

        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            if not self._validate_peer_data(data):
                return False

            peer_id = data["peer_id"]
            info_hash = data["info_hash"]

            if info_hash not in self.peers:
                self.peers[info_hash] = {}

            self.peers[info_hash][peer_id] = {
                "peer_id": peer_id,
                "ip": data["ip"],
                "port": data["port"],
                "downloaded": data.get("downloaded", 0),
                "uploaded": data.get("uploaded", 0),
                "left": data.get("left", 0),
                "is_seeder": data.get("is_seeder", 0) == 0,
                "last_seen": datetime.now(),
            }

            self._cleanup_inactive_peers()
            return True

        except Exception as e:
            self.logger.error(f"Error updating peers: {str(e)}")
            return False

    def _get_peers(self, info_hash: str, max_peers: int = 50) -> list:
        """Get list of peers for a given info_hash.

        Args:
            info_hash: Torrent info hash
            max_peers: Maximum number of peers to return

        Returns:
            list: List of peer dictionaries
        """
        if info_hash not in self.peers:
            return []

        peers = list(self.peers[info_hash].values())
        return peers[:max_peers]

    def _get_swarm_stats(self, info_hash: str) -> tuple:
        """Get seeder and leecher counts for a swarm.

        Args:
            info_hash: Torrent info hash

        Returns:
            tuple: (complete, incomplete) counts
        """
        if info_hash not in self.peers:
            return 0, 0

        complete = sum(1 for p in self.peers[info_hash].values() if p["is_seeder"])
        incomplete = len(self.peers[info_hash]) - complete
        return complete, incomplete

    def register_routes(self) -> Flask:
        """Register Flask routes for the tracker.

        Returns:
            Flask: Configured Flask application
        """
        app = Flask(__name__)

        @app.route("/announce", methods=["GET"])
        def announce():
            """Handle peer announcements."""
            try:
                data = request.get_json()
                if not data or "info_hash" not in data:
                    return jsonify({"failure reason": "Missing required data"}), 400

                updated = self._update_peers(data)
                if not updated:
                    return jsonify({"failure reason": "Invalid peer data"}), 400

                complete, incomplete = self._get_swarm_stats(data["info_hash"])
                peers = self._get_peers(data["info_hash"])

                response_data = {
                    "interval": 120,  # 2 minutes
                    "min interval": 60,
                    "tracker id": self.tracker_id,
                    "complete": complete,
                    "incomplete": incomplete,
                    "peers": peers,
                }
                return jsonify(response_data), 200

            except Exception as e:
                self.logger.error(f"Announce error: {str(e)}")
                return jsonify({"failure reason": "Internal server error"}), 500

        @app.route("/scrape", methods=["GET"])
        def scrape():
            """Handle scrape requests."""
            try:
                data = request.get_json()
                if not data or "info_hash" not in data:
                    return jsonify({"failure reason": "Missing info_hash"}), 400

                complete, incomplete = self._get_swarm_stats(data["info_hash"])

                response_data = {
                    "files": {
                        data["info_hash"]: {
                            "complete": complete,
                            "incomplete": incomplete,
                            "downloaded": complete,  # Simplified
                        }
                    }
                }
                return jsonify(response_data), 200

            except Exception as e:
                self.logger.error(f"Scrape error: {str(e)}")
                return jsonify({"failure reason": "Internal server error"}), 500

        return app

    def run(self) -> None:
        """Run the Flask server."""
        app = self.register_routes()
        self.logger.info(f"Starting tracker on {self.ip}:{self.port}")
        app.run(host=self.ip, port=self.port)


if __name__ == "__main__":
    # Configuration
    TRACKER_CONFIG = {"ip": "0.0.0.0", "port": 8000, "tracker_id": "tracker001"}

    # Create and run tracker
    tracker = Tracker(**TRACKER_CONFIG)
    tracker.run()
