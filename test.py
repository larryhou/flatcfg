#!/usr/bin/env python3
from flatcfg import FixedCodec
import random, struct

def uint(v:int)->int:
    b = struct.pack('i', v)
    return struct.unpack('I', b)[0]

def ulong(v:int)->int:
    b = struct.pack('q', v)
    return struct.unpack('Q', b)[0]

if __name__ == '__main__':
    f = FixedCodec(24)
    v = f.encode(f.min_value)
    print('+', v, struct.pack('>q', v), f.min_value)
    # print(f.decode(v))
    print(f.decode(f.min_memory), f.min_value, hex(f.encode(f.min_value)))
    # print(hex(f.encode(f.max_value)))
    print(f.decode(f.max_memory), f.max_value, hex(f.encode(f.max_value)))

    f32 = FixedCodec(20)
    f64 = FixedCodec(10, 64)
    mask = (1 << 32) - 1
    exit()
    for _ in range(10000):
        v = random.random() * 0xFF
        if random.randrange(0, 2) == 0:
            v = -v
        d = f32.encode(v)
        assert abs(f32.decode(d) - v) <= 0.1
        d = f64.encode(v)
        assert abs(f64.decode(d) - v) <= 0.1

