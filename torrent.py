from lib import *


class Torrent:
    def __init__(self):
        self.torrent_files = []
        self.pieces = []
        self.piece_length: int = 0
        self.name: str = ""
        self.tracker_url: str = ""
        self.files = []
        self.info = {}

    def load_torrent(self, torrent_file):
        """Load metadata from the .torrent file."""
        self.torrent_files.append(torrent_file)

        try:
            with open(torrent_file, "rb") as f:
                torrent_data = bencodepy.decode(f.read())

            # Attempt to load essential torrent data
            try:
                self.tracker_url = torrent_data[b"announce"].decode()
            except KeyError as e:
                print(f"[ERROR] Missing 'announce' key in torrent data: {e}")
                self.tracker_url = ""

            try:
                self.piece_length = torrent_data[b"info"][b"piece_length"]
            except KeyError as e:
                print(f"[ERROR] Missing 'piece_length' key in torrent data: {e}")
                self.piece_length = 0

            try:
                self.pieces = torrent_data[b"info"][b"pieces"]
            except KeyError as e:
                print(f"[ERROR] Missing 'pieces' key in torrent data: {e}")
                self.pieces = 0

            try:
                self.name = torrent_data[b"info"][b"name"].decode()
            except KeyError as e:
                print(f"[ERROR] Missing 'name' key in torrent data: {e}")
                self.name = ""

            try:
                self.info = torrent_data[b"info"]
            except KeyError as e:
                print(f"[ERROR] Missing 'info' key in torrent data: {e}")
                self.info = {}

            # Iterate through files information
            try:
                for file in torrent_data[b"info"][b"files"]:
                    self.files.append(
                        {
                            "length": file[b"length"],
                            "path": [element.decode() for element in file[b"path"]],
                        }
                    )
            except KeyError as e:
                print(f"[ERROR] Missing keys in torrent data: {e}")

        except FileNotFoundError as e:
            print(f"[ERROR] The file {torrent_file} was not found: {e}")
            torrent_data = {}
        except bencodepy.bencode.BencodingError as e:
            print(f"[ERROR] Failed to decode the .torrent file: {e}")
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred: {e}")

    def get_info_hash(self):
        bencoded_info = bencodepy.encode(self.info)
        info_hash = hashlib.sha1(bencoded_info).digest()

        return info_hash
