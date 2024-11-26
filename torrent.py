from lib import *


class Torrent:
    def __init__(self):
        self.torrent_file = ""
        self.json_torrent = {}
        self.tracker_url = ""
        self.name = ""
        self.pieces = []
        self.files = []
        self.piece_length = 0

    def load_torrent(self, torrent_file):
        """Load metadata from the .torrent file."""
        self.torrent_file = torrent_file

        try:
            with open(torrent_file, "rb") as f:
                torrent_data = bencodepy.decode(f.read())

            self.json_torrent = torrent_data
            # Attempt to load essential torrent data
            try:
                self.tracker_url = torrent_data[b"announce"].decode()
            except KeyError as e:
                print(f"[ERROR] Missing 'announce' key in torrent data: {e}")
                self.tracker_url = ""
            try:
                self.piece_length = torrent_data[b"info"][b"piece length"]
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

            # Iterate through files information
            try:
                for file in torrent_data[b"info"][b"files"]:
                    self.files.append(
                        {
                            "length": file[b"length"],
                            "path": file[b"path"][0].decode().replace('\\', '/'),
                        }
                    )
            except KeyError as e:
                print(f"[ERROR] Missing keys in torrent data: {e}")

        except FileNotFoundError as e:
            print(f"[ERROR] The file {torrent_file} was not found: {e}")
            torrent_data = {}
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred: {e}")

    @property
    def info_hash(self):
        try:
            with open(self.torrent_file, "rb") as f:
                torrent_data = f.read()

            start = torrent_data.find(b"4:infod") + len("4:infod") - 1
            end = -1
            print(torrent_data)
            return hashlib.sha1(torrent_data[start:end]).digest()

        except FileNotFoundError as e:
            print(f"[ERROR] The file {self.torrent_file} was not found: {e}")
            torrent_data = {}
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred: {e}")

    @property
    def info(self):
        try:
            with open(self.torrent_file, "rb") as f:
                torrent_data = bencodepy.decode(f.read())

            try:
                info = torrent_data[b"info"]
            except KeyError as e:
                print(f"[ERROR] Missing 'info' key in torrent data: {e}")
                info = {}

            start = 0
            end = 0
            for file in info[b"files"]:
                size = math.ceil(file[b"length"] / self.piece_length)
                end += size
                file["pieces_index"] = list(range(start, end))
                start = end

            return info

        except FileNotFoundError as e:
            print(f"[ERROR] The file {self.torrent_file} was not found: {e}")
            torrent_data = {}
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred: {e}")
