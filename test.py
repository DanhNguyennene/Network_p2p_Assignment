import struct

# Example values
pstr = b"BitTorrent protocol"
pstrlen = len(pstr)  # Length of protocol string (should be 19 for BitTorrent)
reserved = b"\x00" * 8  # 8 bytes of zeroes for reserved field
info_hash = (
    b"\xaa" * 20
)  # Example 20-byte info_hash (in real use, this would be a SHA-1 hash)
peer_id = b"-PC0001-1234567890AB"  # Example 20-byte peer ID

# Pack the handshake
handshake = struct.pack(
    f"!B{pstrlen}s8s20s20s", pstrlen, pstr, reserved, info_hash, peer_id
)
print("Packed handshake:", handshake)

# Now unpack the handshake
# Step 1: Get `pstrlen` from the first byte

# Step 2: Use `pstrlen` to create a format string for unpacking the rest
unpack_format = f"!B{pstrlen}s8s20s20s"

# Step 3: Unpack the data using the format string
unpacked_data = struct.unpack(unpack_format, handshake)

# Display the unpacked values
print("Unpacked Data:")
print("pstrlen:", unpacked_data[0])
print("pstr:", unpacked_data[1].decode())
print("reserved:", unpacked_data[2])
print("info_hash:", unpacked_data[3])
print("peer_id:", unpacked_data[4].decode())
