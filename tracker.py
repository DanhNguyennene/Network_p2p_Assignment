from lib import *

# File - Pieces map
#

app = Flask(__name__)


class TrackerNode:
    def __init__(self, tracker_id, ip, port):
        self.tracker_id = tracker_id
        self.ip = ip
        self.port = port
        self.peers = {}
        # self.file_to_pieces =

    def create_file_to_pieces():

    @app.route("/announce", methods=["POST"])
    def announce(self):
        """
        Endpoint for peers to register themselves and their files.
        """
        data = request.json

        peer_id = data.get("peer_id")
        ip = data.get("ip")
        port = data.get("port")
        num_pieces = data.get("num_pieces")

        if peer_id and ip and port and num_pieces:
            self.peers[peer_id] = {
                "peer_id": peer_id,
                "ip": ip,
                "port": port,
                "num_pieces": num_pieces,
            }
            return jsonify({"status": "registered"}), 200
        return jsonify({"error": "Invalid data"}), 400

    @app.route("/get_peers", methods=["GET"])
    def get_peers():
        """
        Returns a list of peers that have the requested file.
        """
        file_hash = request.args.get("file_hash")
        available_peers = [
            {"peer_id": peer_id, "ip": peer["ip"], "port": peer["port"]}
            for peer_id, peer in peers.items()
            if file_hash in peer["files"]
        ]
        return jsonify({"peers": available_peers}), 200

    def run(self):
        app.run(host=self.ip, port=self.port)


if __name__ == "__main__":
    ip = "0.0.0.0"
    port = 8000
    tracker = TrackerNode(ip, port)
    tracker.run()
