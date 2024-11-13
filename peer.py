import requests
import socket
import threading
import os

TRACKER_URL = 'http://localhost:8000'

class PeerNode:
    def __init__(self, peer_id, ip, port, shared_files):
        self.peer_id = peer_id
        self.ip = ip
        self.port = port
        self.shared_files = shared_files
        self.downloaded_files = {}
    
    def register_with_tracker(self):
        """Registers the peer with the tracker."""
        data = {
            "peer_id": self.peer_id,
            "ip": self.ip,
            "port": self.port,
            "files": list(self.shared_files.keys())
        }
        response = requests.post(f"{TRACKER_URL}/announce", json=data)
        if response.status_code == 200:
            print(f"Registered with tracker: {response.json()}")
        else:
            print(f"Failed to register: {response.text}")

    def download_file(self, file_hash):
        """Downloads a file from other peers."""
        response = requests.get(f"{TRACKER_URL}/get_peers", params={"file_hash": file_hash})
        if response.status_code != 200:
            print("Failed to fetch peers.")
            return
        
        peers = response.json().get('peers', [])
        if not peers:
            print("No peers available for this file.")
            return
        
        for peer in peers:
            threading.Thread(target=self.request_file, args=(peer['ip'], peer['port'], file_hash)).start()

    def request_file(self, ip, port, file_hash):
        """Connects to a peer and requests a file."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((ip, port))
                s.sendall(file_hash.encode())
                with open(f"downloaded_{file_hash}.dat", 'wb') as f:
                    while True:
                        data = s.recv(1024)
                        if not data:
                            break
                        f.write(data)
                print(f"File {file_hash} downloaded from {ip}:{port}")
        except Exception as e:
            print(f"Error downloading file: {e}")

    def start_server(self):
        """Starts a peer server to upload files to others."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.ip, self.port))
        server.listen()
        print(f"Peer listening on {self.ip}:{self.port}")

        while True:
            conn, addr = server.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr)).start()

    def handle_client(self, conn, addr):
        """Handles file upload requests from other peers."""
        file_hash = conn.recv(1024).decode()
        if file_hash in self.shared_files:
            file_path = self.shared_files[file_hash]
            with open(file_path, 'rb') as f:
                conn.sendfile(f)
        conn.close()

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
    
    threading.Thread(target=peer.start_server).start()
    
    peer.download_file("file1_hash")

if __name__ == '__main__':
    run_peer()

