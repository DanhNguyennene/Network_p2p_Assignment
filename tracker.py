from flask import Flask, request, jsonify

class TrackerNode:
    def __init__(self, tracker_id, ip, port):
        self.tracker_id = tracker_id
        self.ip = ip
        self.port = port
        self.peers = {}  # Dictionary to store peer information
        self.file_to_pieces = {}  # Dictionary to store file-to-pieces mapping

    def create_file_to_pieces(self, file_hash, num_pieces):
        """
        Create an entry for a file with its pieces.
        """
        if file_hash not in self.file_to_pieces:
            self.file_to_pieces[file_hash] = [False] * num_pieces

    def register_routes(self):
        """Register Flask routes within the class context."""
        app = Flask(__name__)

        @app.route("/announce", methods=["POST"])
        def announce():
            """
            Endpoint for peers to register themselves and their files.
            """
            data = request.json
            peer_id = data.get("peer_id")
            ip = data.get("ip")
            port = data.get("port")
            file_hash = data.get("file_hash")
            pieces = data.get("pieces", [])
            downloaded = data.get("downloaded", 0)
            uploaded = data.get("uploaded", 0)
            is_seeder = data.get("is_seeder", False)

            if peer_id and ip and port and file_hash:
                # Register the peer
                if file_hash not in self.peers:
                    self.peers[file_hash] = {}

                self.peers[file_hash][peer_id] = {
                    "ip": ip,
                    "port": port,
                    "pieces": pieces,
                    "downloaded": downloaded,
                    "uploaded": uploaded,
                    "is_seeder": is_seeder
                }
                print(f"Registered peer {peer_id} for file {file_hash}")
                return jsonify({"status": "registered"}), 200

            return jsonify({"error": "Invalid data"}), 400

        @app.route("/get_peers", methods=["GET"])
        def get_peers():
            """
            Returns a list of peers that have the requested file.
            """
            file_hash = request.args.get("file_hash")
            if file_hash in self.peers:
                available_peers = [
                    {"peer_id": peer_id, "ip": peer["ip"], "port": peer["port"], "pieces": peer["pieces"], "is_seeder": peer["is_seeder"]}
                    for peer_id, peer in self.peers[file_hash].items()
                ]
                return jsonify(available_peers), 200
            return jsonify([]), 200

        return app

    def run(self):
        """Run the Flask server."""
        app = self.register_routes()
        app.run(host=self.ip, port=self.port)

if __name__ == "__main__":
    ip = "0.0.0.0"
    port = 8000
    tracker_id = "tracker001"
    
    # Create a TrackerNode instance
    tracker = TrackerNode(tracker_id, ip, port)
    tracker.run()