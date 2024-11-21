import struct


class MessageFactory:
    @staticmethod
    def handshake(info_hash, peer_id):
        pstr = b"BitTorrent protocol"
        reserved = b"\x00" * 8  # 8 zero bytes for reserved field
        pstrlen = len(pstr)  # Length of the protocol string, usually 19

        handshake = struct.pack(
            f"!IB{pstrlen}s8s20s20s",
            19,
            pstrlen,
            pstr,
            reserved,
            info_hash,
            peer_id,
        )
        return handshake

    @staticmethod
    def keep_alive():
        """Keep-alive message: <len=0000>"""
        return struct.pack("!I", 0)  # Length prefix of 0, no message ID or payload

    @staticmethod
    def choke():
        """Choke message: <len=0001><id=0>"""
        return struct.pack("!IB", 1, 0)  # Length prefix of 1, ID of 0

    @staticmethod
    def unchoke():
        """Unchoke message: <len=0001><id=1>"""
        return struct.pack("!IB", 1, 1)  # Length prefix of 1, ID of 1

    @staticmethod
    def interested():
        """Interested message: <len=0001><id=2>"""
        return struct.pack("!IB", 1, 2)  # Length prefix of 1, ID of 2

    @staticmethod
    def not_interested():
        """Not interested message: <len=0001><id=3>"""
        return struct.pack("!IB", 1, 3)  # Length prefix of 1, ID of 3

    @staticmethod
    def have(piece_index):
        """Have message: <len=0005><id=4><piece index>"""
        return struct.pack(
            "!IBI", 5, 4, piece_index
        )  # Length prefix of 5, ID of 4, piece index

    @staticmethod
    def request_bitfield():
        """Bitfield message: <len=0001+X><id=5><bitfield>"""
        return struct.pack("!IB", 1, 5)
    @staticmethod
    def bitfield(bitfield):
        """Bitfield message: <len=0001+X><id=5><bitfield>"""
        bitfield_length = len(bitfield)
        return struct.pack(f"!IB{bitfield_length}s", 1 + bitfield_length, 5, bitfield)

    @staticmethod
    def request(index, begin, length):
        """Request message: <len=0013><id=6><index><begin><length>"""
        return struct.pack(
            "!IBIII", 13, 6, index, begin, length
        )  # Length prefix of 13, ID of 6

    @staticmethod
    def piece(index, begin, block):
        """Piece message: <len=0009+X><id=7><index><begin><block>"""
        block_length = len(block)
        return struct.pack(
            f"!IBII{block_length}s", 9 + block_length, 7, index, begin, block
        )
    @staticmethod
    def dont_have_piece():
        """dont_have_piece message: <len=0001+X><id=10>"""
        return struct.pack("!IB", 1, 10)
    @staticmethod
    def cancel(index, begin, length):
        """Cancel message: <len=0013><id=8><index><begin><length>"""
        return struct.pack(
            "!IBIII", 13, 8, index, begin, length
        )  # Length prefix of 13, ID of 8

    @staticmethod
    def port(listen_port):
        """Port message: <len=0003><id=9><listen-port>"""
        return struct.pack(
            "!IBH", 3, 9, listen_port
        )  # Length prefix of 3, ID of 9, port


class MessageParser:
    @staticmethod
    def parse_message(data):
        """
        Parses a received message from a peer.
        Returns a dictionary with message details.
        """
        # Minimum length for a valid message (keep-alive)
        if len(data) < 4:
            raise ValueError("Invalid message length")

        # Read the message length prefix (first 4 bytes)
        length_prefix = struct.unpack("!I", data[:4])[0]

        # Keep-alive message (length = 0)
        if length_prefix == 0:
            return {"type": "keep_alive"}
        if length_prefix == 19:
            data = data[4:]
            pstrlen = struct.unpack("!B", data[:1])[0]
            protocol, reserved, info_hash, peer_id = struct.unpack(
                f"!{pstrlen}s8s20s20s", data[1 : 1 + pstrlen + 48]
            )
            return {
                "type": "handshake",
                "protocol": protocol.decode(),
                "reserved": reserved,
                "info_hash": info_hash,
                "peer_id": peer_id,
            }

        # Read message ID (1 byte after the length prefix)
        message_id = struct.unpack("!B", data[4:5])[0]

        # Depending on message_id, interpret the rest of the message
        message_map = {
            0: "choke",
            1: "unchoke",
            2: "interested",
            3: "not_interested",
            4: "have",
            5: "bitfield",
            6: "request",
            7: "piece",
            8: "cancel",
            9: "port",
            10: "dont_have_piece",
        }

        # Check for valid message ID
        if message_id not in message_map:
            raise ValueError("Unknown message ID")

        message_type = message_map[message_id]
        payload = data[5:]  # Remaining bytes after message_id

        # Parse based on message type
        if message_type == "have":
            piece_index = struct.unpack("!I", payload)[0]
            return {"type": "have", "piece_index": piece_index}

        elif message_type == "bitfield":
            return {"type": "bitfield", "bitfield": payload}

        elif message_type == "request":
            index, begin, length = struct.unpack("!III", payload)
            return {"type": "request", "index": index, "begin": begin, "length": length}

        elif message_type == "piece":
            index, begin = struct.unpack("!II", payload[:8])
            block = payload[8:]
            return {"type": "piece", "index": index, "begin": begin, "block": block}

        elif message_type == "cancel":
            index, begin, length = struct.unpack("!III", payload)
            return {"type": "cancel", "index": index, "begin": begin, "length": length}

        elif message_type == "port":
            listen_port = struct.unpack("!H", payload)[0]
            return {"type": "port", "listen_port": listen_port}
        elif message_type == "dont_have_piece":
            return {"type": "dont_have_piece"}
        
        else:
            # Messages like choke, unchoke, interested, not_interested
            return {"type": message_type}
