from flask import Flask, request, jsonify
import threading

app = Flask(__name__)

peers = {}

@app.route('/announce', methods=['POST'])
def announce():
    """
    Endpoint for peers to register themselves and their files.
    """
    data = request.json
    peer_id = data.get('peer_id')
    ip = data.get('ip')
    port = data.get('port')
    files = data.get('files', [])
    
    if peer_id and ip and port:
        peers[peer_id] = {
            'ip': ip,
            'port': port,
            'files': files
        }
        return jsonify({"status": "registered"}), 200
    return jsonify({"error": "Invalid data"}), 400

@app.route('/get_peers', methods=['GET'])
def get_peers():
    """
    Returns a list of peers that have the requested file.
    """
    file_hash = request.args.get('file_hash')
    available_peers = [
        {"peer_id": peer_id, "ip": peer['ip'], "port": peer['port']}
        for peer_id, peer in peers.items() if file_hash in peer['files']
    ]
    return jsonify({"peers": available_peers}), 200

def run_tracker():
    app.run(host='0.0.0.0', port=8000)

if __name__ == '__main__':
    run_tracker()

