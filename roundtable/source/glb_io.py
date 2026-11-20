import json
import struct


def unpack(path):
    data = path.read_bytes()
    magic, version, total, size, chunk = struct.unpack_from('<4s4I', data)
    assert (magic, version, total, chunk) == (b'glTF', 2, len(data), 0x4E4F534A)
    return json.loads(data[20:20 + size]), data[20 + size:]


def pack(scene, binary):
    metadata = json.dumps(scene, ensure_ascii=False, separators=(',', ':')).encode()
    metadata += b' ' * (-len(metadata) % 4)
    header = struct.pack('<4s4I', b'glTF', 2, 20 + len(metadata) + len(binary),
                         len(metadata), 0x4E4F534A)
    return header + metadata + binary
