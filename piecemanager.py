import os
import hashlib
import bencodepy


class PieceManager:
    def __init__(self, torrent_file, file_dir):
        """
        Initialize the PieceManager with a .torrent file and download directory.

        Args:
            torrent_file (str): Path to the .torrent file.
            dir (str): Directory where the files will be saved/to upload.
        """
        self.torrent_file = torrent_file
        self.file_dir = file_dir
        self.bitfield = []
        self.completed_pieces = set()
        self.piece_length = 0
        self.total_pieces = 0
        self.pieces_hash = []
        self.pieces_dict = {}
        self.files = []
        self._load_torrent()
        self._split_files_into_pieces()
        self._initialize_bitfield()

    def _split_files_into_pieces(self):
        """
        Split each file in self.files into pieces based on self.piece_length.

        Returns:
            dict: A dictionary where each key is an integer (piece index) and each value is a dictionary
                with 'file' (filename) and 'length' (length of the piece).

                {
                    0: {"file": "file1.txt", "length": piece_length},
                    1: {"file": "file1.txt", "length": piece_length},
                    2: {"file": "file1.txt", "length": piece_length_of_last_chunk},
                    3: {"file": "file2.txt", "length": piece_length},
                    4: {"file": "file2.txt", "length": piece_length_of_last_chunk},
                }
        """
        piece_index = 0

        for file_info in self.files:
            file_name = file_info["path"]
            file_length = file_info["length"]
            offset = 0

            # Split the file into pieces of size self.piece_length
            while offset < file_length:
                # Determine the length of the current piece
                current_piece_length = min(self.piece_length, file_length - offset)
                self.pieces_dict[piece_index] = {
                    "file": file_name,
                    "length": current_piece_length,
                }
                offset += current_piece_length
                piece_index += 1

    def _load_torrent(self):
        """Load metadata from the .torrent file."""
        try:
            torrent_data = self.torrent_file.json_torrent
            print(f"[INFO] Loading torrent file: {torrent_data}")
            # Extract essential metadata
            self.piece_length = torrent_data[b"info"][b"piece_length"]
            self.pieces_hash = torrent_data[b"info"][b"pieces"]
            self.total_pieces = (
                len(self.pieces_hash) // 20
            )  # SHA1 hash size is 20 bytes

            # Load files information
            if b"files" in torrent_data[b"info"]:
                for file_info in torrent_data[b"info"][b"files"]:
                    parent_dir = os.path.join(
                        self.file_dir, torrent_data[b"info"][b"name"].decode()
                    )
                    file_path = os.path.join(parent_dir, file_info[b"path"].decode())
                    self.files.append(
                        {"length": file_info[b"length"], "path": file_path}
                    )
            else:
                file_path = os.path.join(
                    self.file_dir, torrent_data[b"info"][b"name"].decode()
                )
                self.files.append(
                    {"length": torrent_data[b"info"][b"length"], "path": file_path}
                )

            print(f"[INFO] Loaded .torrent file: {self.torrent_file}")
            print(
                f"[INFO] Total pieces: {self.total_pieces}, Piece length: {self.piece_length}"
            )

        except Exception as e:
            print(f"[ERROR] Failed to load torrent file: {e}")

    def get_total_pieces(self):
        """Get the total number of pieces in the torrent."""
        return self.total_pieces

    def _initialize_bitfield(self):
        """Initialize the bitfield based on local storage."""
        self.bitfield = [0] * self.total_pieces

        # Check which pieces are already downloaded
        for index in range(self.total_pieces):
            if self.is_piece_complete(index):
                self.bitfield[index] = 1
                self.completed_pieces.add(index)

    def is_piece_complete(self, index):
        """Check if a specific piece is already downloaded."""
        piece_data = self.get_piece(index)
        if piece_data:
            expected_hash = self.pieces_hash[index * 20 : (index + 1) * 20]
            actual_hash = hashlib.sha1(piece_data).digest()
            return actual_hash == expected_hash
        return False

    def get_piece(self, index):
        """
        Retrieve a piece by its index, handling multiple files if necessary.

        Args:
            index (int): The index of the piece to retrieve.

        Returns:
            bytes: The data for the requested piece, or None if an error occurs.
        """
        try:
            # Retrieve the file and piece length information from the pieces dictionary
            piece_info = self.pieces_dict.get(index)
            if piece_info is None:
                print(f"[ERROR] Piece index {index} does not exist.")
                return None

            file_path = piece_info["file"]
            print(f"[INFO] Retrieving piece {index} from file: {file_path}")
            piece_length = piece_info["length"]

            # Open the file in binary read mode
            if not os.path.exists(file_path):
                print(f"[INFO] File {file_path} is yet yo be exist.")
                return None
            with open(file_path, "rb") as file:
                # Calculate the start position for the piece within the file.
                # If it's a new file, start from 0; otherwise, use the index.
                start_index = 0
                for idx, info in self.pieces_dict.items():
                    if idx == index:
                        break
                    if info["file"] == file_path:
                        start_index += 1
                    else:
                        start_index = 0

                # Calculate the start position of the piece within the file
                start = start_index * self.piece_length
                file.seek(start)

                # Read the exact length of the piece
                piece_data = file.read(piece_length)

                # Verify that the retrieved piece is the correct size
                if len(piece_data) != piece_length:
                    print(
                        f"[ERROR] Incomplete piece {index}. Expected {piece_length} bytes, got {len(piece_data)} bytes."
                    )
                    return None

            return piece_data

        except Exception as e:
            print(f"[ERROR] An error occurred while retrieving piece {index}: {e}")
            return None

    def save_piece(self, index, data):
        """
        Save a downloaded piece to the appropriate file(s), creating files if necessary.

        Args:
            index (int): The index of the piece.
            data (bytes): The data to save.
        """
        # Retrieve the piece info from the pieces dictionary
        piece_info = self.pieces_dict.get(index)
        if piece_info is None:
            print(f"[ERROR] Piece index {index} does not exist.")
            return

        file_path = piece_info["file"]
        piece_length = piece_info["length"]
        # Ensure the directory for the file exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Find the total size of the file associated with this piece
        file_size = None
        for file_info in self.files:
            if file_info["path"] == file_path:
                file_size = file_info["length"]
                break

        if not os.path.exists(file_path):
            with open(file_path, "wb") as f:
                if file_size is not None:
                    f.truncate(file_size)

        # Open the file in read and write binary mode
        with open(file_path, "r+b") as file:
            # Calculate the correct start position within the file
            start_index = 0
            for idx, info in self.pieces_dict.items():
                if idx == index:
                    break
                if info["file"] == file_path:
                    start_index += 1
                else:
                    start_index = 0

            # Move to the correct starting position and write the data
            start = start_index * self.piece_length
            file.seek(start)

            file.write(data[:piece_length])

        # Mark as complete and verify
        # self.mark_piece_completed(index)
        if not self.verify_piece(index):
            print(f"[ERROR] Piece {index} failed verification after saving.")
        else:
            print(f"[DEBUG] Saved and verified piece {index}, length: {len(data)}")

    def verify_piece(self, index):
        """
        Verify a specific piece by its index.

        Args:
            index (int): The index of the piece to verify.

        Returns:
            bool: True if the piece is verified, False otherwise.
        """
        # Retrieve the piece data using the existing get_piece() method
        piece_data = self.get_piece(index)
        if not piece_data:
            print(f"[ERROR] Could not read piece {index}")
            return False

        # Calculate the SHA-1 hash of the piece
        expected_hash = self.pieces_hash[index * 20 : (index + 1) * 20]
        actual_hash = hashlib.sha1(piece_data).digest()

        # Compare the actual hash with the expected hash
        if actual_hash == expected_hash:
            self.mark_piece_completed(index)
            print(f"[INFO] Verified piece {index} successfully.")
            return True
        else:
            print(f"[ERROR] Verification failed for piece {index}.")
            return False

    def mark_piece_completed(self, index):
        """Mark a specific piece as completed."""
        self.bitfield[index] = 1
        self.completed_pieces.add(index)
        print(f"[INFO] Piece {index} marked as completed")

    def verify_all_pieces(self):
        """
        Verify all pieces sequentially.

        Returns:
            int: The number of verified pieces.
        """
        verified_count = 0
        for index in range(self.total_pieces):
            if self.verify_piece(index):
                verified_count += 1
        print(f"[INFO] Verified {verified_count}/{self.total_pieces} pieces.")
        return verified_count

    def get_next_missing_piece(self):
        """Get the next missing piece to download."""
        print(f"[INFO] Bitfield: {self.bitfield}")
        print(f"total pieces: {self.total_pieces}")
        for i in range(self.total_pieces):
            if self.bitfield[i] == 0:
                return i
        print(f"[INFO] All pieces have been downloaded!!!!!!!!!!!!!!!")
        return None

    def get_bitfield(self):
        """Get the current bitfield."""
        return self.bitfield

    def update_bitfield(self, bitfield):
        """Update the bitfield with information from another peer."""
        for i in range(min(self.total_pieces, len(bitfield))):
            if bitfield[i] == 1 and self.bitfield[i] == 0:
                self.mark_piece_completed(i)
