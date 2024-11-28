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
        self.pieces_dict_origin = {}
        self.local_pieces_dict = {}
        self.files = []
        self._load_torrent()
        self._map_pieces_to_files()
        self._map_local_pieces_to_files()   
        self._initialize_bitfield()
    def _map_pieces_to_files(self):
        """
        Map torrent pieces to their original files, tracking the file, length, and offset 
        for each piece across multiple files.
        """
        piece_length = self.piece_length
        self.pieces_dict_origin = {}

        file_index = 0
        file_offset = 0
        
        for piece_index in range(self.total_pieces):
            # Reset piece-specific tracking for each piece
            piece_remaining = piece_length
            piece_origins = []

            # Continue until we've filled the entire piece
            while piece_remaining > 0 and file_index < len(self.files):
                current_file = self.files[file_index]
                file_name = current_file["path"]
                file_length = current_file["length"]

                # Calculate how much we can take from the current file
                available_in_file = file_length - file_offset
                take_from_file = min(piece_remaining, available_in_file)

                if take_from_file > 0:
                    # Add file contribution to this piece
                    piece_origins.append({
                        "file": file_name,
                        "length": take_from_file,
                        "offset": file_offset,
                    })

                    # Update tracking variables
                    piece_remaining -= take_from_file
                    file_offset += take_from_file

                # Move to next file if current file is exhausted
                if file_offset >= file_length:
                    file_index += 1
                    file_offset = 0

            # Store the piece origins
            self.pieces_dict_origin[piece_index] = piece_origins

        print(f"[INFO] Mapped {self.total_pieces} pieces to their origin files.")
        return self.pieces_dict_origin
    def _map_local_pieces_to_files(self):
        """
        Maps local pieces to their origin files, tracking the file, length, and offset 
        for each piece across multiple local files.
        5 piece, mot so file, 1 piêc sẽ map qua các file, ánh xạ 1-n
        1- file1, file2
        2- file2 (continue), file3
        sẽ có ofset để biết đọc từ đâu
        piece leng mặc định là 512kb = 1024*512
        sẽ có file bị segment, lỗi, nó sẽ skip cái piece đó lun
        đó, mất file r, nó skip piêc lun
        ví dụ sai file , nó sẽ hash để so sánh, nếu sai nó skip lun
        """
        piece_length = self.piece_length
        self.local_pieces_dict = {}

        file_index = 0
        file_offset = 0
        
        for piece_index in range(self.total_pieces):
            # Reset piece-specific tracking for each piece
            piece_remaining = piece_length
            piece_origins = []
            if file_index >= len(self.files):
                print(f"[ERROR] No more files available. Skipping piece {piece_index}.")
                break
            if not os.path.exists(self.files[file_index]["path"]):
                print(f"[ERROR] File {self.files[file_index]["path"]} does not exist.Skipping piece {piece_index}.")
                if piece_index+1 < self.total_pieces:
                    file_offset += self.pieces_dict_origin[piece_index+1][0]['offset']
                    file_index+=1
                    continue    
                else:
                    print(f"[ERROR] File {self.files[file_index]["path"]} does not exist.Skipping piece {piece_index}.")
                    break

            # Continue until we've filled the entire piece
            piece_data = b""
            while piece_remaining > 0 and file_index < len(self.files):
                current_file = self.files[file_index]
                file_name = current_file["path"]
                if not os.path.exists(self.files[file_index]["path"]):
                    break
                file_length = current_file["length"]

                # Calculate how much we can take from the current file
                available_in_file = file_length - file_offset
                take_from_file = min(piece_remaining, available_in_file)

                piece_remaining -= take_from_file
                if take_from_file > 0:
                    # Add file contribution to this piece
                    piece_origins.append({
                        "file": file_name,
                        "length": take_from_file,
                        "offset": file_offset,
                    })

                    # Open the file and read the piece
                    with open(file_name, 'rb') as file:
                        file.seek(file_offset)
                        piece_data += file.read(take_from_file)
                        if piece_data and piece_remaining == 0:
                            expected_hash = self.pieces_hash[piece_index * 20 : (piece_index + 1) * 20]
                            actual_hash = hashlib.sha1(piece_data).digest()
                            if actual_hash != expected_hash:
                                print(f"[ERROR] Piece {piece_index} is corrupted. Skipping.")
                                # remove the last file contribution
                                if len(piece_origins) > 0:
                                    piece_origins.pop()
                                file_offset += self.pieces_dict_origin[piece_index+1][0]['offset']
                                continue

                    # Update tracking variables
                    file_offset += take_from_file

                # Move to next file if current file is exhausted
                if file_offset >= file_length:
                    file_index += 1
                    file_offset = 0

            # Store the piece origins
            self.local_pieces_dict[piece_index] = piece_origins

        print(f"[INFO] Mapped {self.total_pieces} local pieces to their origin files.")
        return self.local_pieces_dict




    def _load_torrent(self):
        """Load metadata from the .torrent file."""
        try:
            torrent_data = self.torrent_file.json_torrent
            print(f"[INFO] Loading torrent file: {torrent_data}")
            # Extract essential metadata
            self.piece_length = torrent_data[b"info"][b"piece length"]
            self.pieces_hash = torrent_data[b"info"][b"pieces"]
            print(f"[INFO] Piece length: {self.piece_length}, Pieces hash: {self.pieces_hash}")
            self.total_pieces = (
                len(self.pieces_hash) // 20
            )  # SHA1 hash size is 20 bytes

            # Load files information
            if b"files" in torrent_data[b"info"]:
                for file_info in torrent_data[b"info"][b"files"]:
                    parent_dir = os.path.join(self.file_dir, torrent_data[b"info"][b"name"].decode())
                    file_path = os.path.join(parent_dir, *[path.decode() for path in file_info[b"path"]])
                    print(f"[INFO] File path: {file_path}")
                    self.files.append(
                        {"length": file_info[b"length"], "path": file_path}
                    )
            else:
                file_path = self.file_dir
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
    def get_piece_length(self,index):
        """Get the length of each piece."""
        return sum(self.pieces_dict_origin[index][i]['length'] for i in range(len(self.pieces_dict_origin[index])))
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
        Retrieve a piece by its index, handling multiple files and file offsets.
        
        Args:
            index (int): The index of the piece to retrieve.

        Returns:
            bytes: The data for the requested piece, or None if an error occurs.
        """
        try:
            # Retrieve the piece information from the local_pieces_dict
            piece_info = self.local_pieces_dict.get(index)
            if not piece_info:
                print(f"[ERROR] get_piece() - Piece {index} not found in local_pieces_dict.")
                return None


            piece_data = b""
            if not piece_info:
                print(f"[ERROR] get_piece() - Piece {index} not found in local_pieces_dict.")
                return None
            for file_info in piece_info:
                file_path = file_info["file"]
                file_length = file_info["length"]
                offset = file_info["offset"]
                
                if not os.path.exists(file_path):
                    print(f"[ERROR] get_piece() - File {file_path} does not exist.")
                    return None  # If any file doesn't exist, return None for the whole piece


                with open(file_path, "rb") as file:
                    file.seek(offset)

                    # Calculate how much data we can read from this file

                    data = file.read(file_length)

                    # Add the data to the cumulative piece data
                    piece_data += data

            return piece_data

        except Exception as e:
            print(f"[ERROR] get_piece() - Error occurred while retrieving piece {index}: {e}")
            return None



    def save_piece(self, index, data):
        """
        Save a downloaded piece to the appropriate file(s), creating files if necessary.

        Args:
            index (int): The index of the piece.
            data (bytes): The data to save.
        """
        # Retrieve the piece info from the local_pieces_dict
        piece_info = self.pieces_dict_origin.get(index)
        if piece_info is None:
            print(f"[ERROR] Piece index {index} does not exist in local_pieces_dict.")
            return

        # Iterate over the list of file information for the piece
        for file_info in piece_info:
            file_path = file_info["file"]
            piece_length = file_info["length"]
            offset = file_info["offset"]

            # Ensure the directory for the file exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Find the total size of the file associated with this piece
            file_size = None
            for file_data in self.files:
                if file_data["path"] == file_path:
                    file_size = file_data["length"]
                    break

            # If the file doesn't exist, create it and set its size
            if not os.path.exists(file_path):
                with open(file_path, "wb") as f:
                    if file_size is not None:
                        f.truncate(file_size)

            # Open the file in read and write binary mode
            with open(file_path, "r+b") as file:
                # Move to the correct starting position within the file
                file.seek(offset)

                # Write the data to the correct position in the file
                data_to_write = data[:piece_length]
                file.write(data_to_write)

                # Remove the written part from the data
                data = data[piece_length:]

            # After writing, if all data has been written, break out of the loop
            if len(data) == 0:
                break
        self._map_local_pieces_to_files()

        # Mark as complete and verify the saved piece
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
        expected_hash = self.pieces_hash[index * 20 : (index + 1) * 20]  # Assuming 20-byte hashes
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
        self._map_local_pieces_to_files()
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
        missing_pieces = [i for i in range(self.total_pieces) if self.bitfield[i] == 0]
        print(f"[DEBUG] Missing pieces: {self.bitfield}")
        if missing_pieces:
            return missing_pieces
        else:
            print(f"[INFO] All pieces have been downloaded!")
            return None

    def get_bitfield(self):
        """Get the current bitfield."""
        return bytes(self.bitfield)

    def update_bitfield(self, bitfield):
        """Update the bitfield with information from another peer."""
        for i in range(min(self.total_pieces, len(bitfield))):
            if bitfield[i] == 1 and self.bitfield[i] == 0:
                self.mark_piece_completed(i)
