import os
import hashlib
import bencodepy

class PieceManager:
    def __init__(self, torrent_file,file_dir):
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
        self.files = []
        self.load_torrent()
        self.initialize_bitfield()

    def load_torrent(self):
        """Load metadata from the .torrent file."""
        try:
            torrent_data = self.torrent_file.json_torrent
            print(f"[INFO] Loading torrent file: {torrent_data}")
            # Extract essential metadata
            self.piece_length = torrent_data[b'info'][b'piece_length']
            self.pieces_hash = torrent_data[b'info'][b'pieces']
            self.total_pieces = len(self.pieces_hash) // 20  # SHA1 hash size is 20 bytes
            
            # Load files information
            if b'files' in torrent_data[b'info']:
                for file_info in torrent_data[b'info'][b'files']:
                    parent_dir = os.path.join(self.file_dir, torrent_data[b'info'][b'name'].decode())
                    print(file_info[b'path'][0])
                    file_path = os.path.join(parent_dir, file_info[b'path'][0].decode())
                    print(file_path)
                    self.files.append({
                        'length': file_info[b'length'],
                        'path': file_path
                    })  
            else:
                file_path = os.path.join(self.file_dir, torrent_data[b'info'][b'name'].decode())
                self.files.append({'length': torrent_data[b'info'][b'length'], 'path': file_path})

            print(f"[INFO] Loaded .torrent file: {self.torrent_file}")
            print(f"[INFO] Total pieces: {self.total_pieces}, Piece length: {self.piece_length}")

        except Exception as e:
            print(f"[ERROR] Failed to load torrent file: {e}")
    def get_total_pieces(self):
        """Get the total number of pieces in the torrent."""
        return self.total_pieces
    
    def initialize_bitfield(self):
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
            expected_hash = self.pieces_hash[index * 20:(index + 1) * 20]
            actual_hash = hashlib.sha1(piece_data).digest()
            return actual_hash == expected_hash
        return False


    def get_piece(self, index):
        """
        Retrieve a piece by its index, handling multiple files.
        
        Args:
            index (int): The index of the piece to retrieve.
            
        Returns:
            bytes: The data for the requested piece, or None if an error occurs.
        """
        try:
            start = index * self.piece_length
            piece_data = b""

            # Iterate over the list of files
            for file_info in self.files:
                file_path = file_info['path']
                print(f"[INFO] Reading piece {index} from {file_path}")
                file_size = file_info['length']

                # Check if the current file exists and contains the start position
                if not os.path.exists(file_path):
                    print(f"[INFO] File not found: {file_path}. Piece {index} is not available yet.")
                    return None

                if start >= file_size:
                    start -= file_size
                    continue

                # Open the file and seek to the correct position
                with open(file_path, "rb") as file:
                    file.seek(start)
                    remaining_length = self.piece_length - len(piece_data)
                    piece_data += file.read(remaining_length)
                    
                    # Break if we've read the entire piece
                    if len(piece_data) >= self.piece_length:
                        break

                # Reset the start to 0 for subsequent files
                start = 0

            return piece_data if len(piece_data) > 0 else None

        except Exception as e:
            print(f"[ERROR] Error reading piece {index}: {e}")
            return None


    def save_piece(self, index, data):
        """
        Save a downloaded piece to the appropriate file, creating files if necessary.
        
        Args:
            index (int): The index of the piece.
            data (bytes): The data to save.
        """
        start = index * self.piece_length
        offset = 0

        for file_info in self.files:
            file_path = file_info['path']
            file_size = file_info['length']

            # Create the file if it does not exist
            if not os.path.exists(file_path):
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "wb") as f:
                    f.truncate(file_size)  # Pre-allocate the file size

            if start >= file_size:
                start -= file_size
                continue

            # Open the file in read-write mode and write the data
            with open(file_path, "r+b") as file:
                file.seek(start)
                write_size = min(len(data) - offset, file_size - start)
                file.write(data[offset:offset + write_size])
                offset += write_size

                if offset >= len(data):
                    break

        # Mark the piece as completed after saving
        self.mark_piece_completed(index)
        print(f"[DEBUG] Saved piece {index}, length: {len(data)}")


    def mark_piece_completed(self, index):
        """Mark a specific piece as completed."""
        self.bitfield[index] = 1
        self.completed_pieces.add(index)
        print(f"[INFO] Piece {index} marked as completed")

    def get_next_missing_piece(self):
        """Get the next missing piece to download."""
        print(f"[INFO] Bitfield: {self.bitfield}")
        print(f"total pieces: {self.total_pieces}")
        for i in range(self.total_pieces):
            if self.bitfield[i] == 0:
                return i
        return None

    def get_bitfield(self):
        """Get the current bitfield."""
        return bytes(self.bitfield)

    def update_bitfield(self, bitfield):
        """Update the bitfield with information from another peer."""
        for i in range(min(self.total_pieces, len(bitfield))):
            if bitfield[i] == 1 and self.bitfield[i] == 0:
                self.mark_piece_completed(i)
