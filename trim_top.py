#!/usr/bin/env python3
"""Estadistica de tamanos de funcion y recorte: conserva solo las K funciones MAS GRANDES (el resto -> unreachable).
Uso: python3 trim_top.py entrada.wasm salida.wasm K   |   python3 trim_top.py entrada.wasm - 0  (solo estadisticas)"""
import sys
def rleb(d, p):
    r = s = 0
    while True:
        b = d[p]; p += 1
        r |= (b & 0x7f) << s; s += 7
        if not b & 0x80: return r, p
def wleb(n):
    o = bytearray()
    while True:
        b = n & 0x7f; n >>= 7
        if n: o.append(b | 0x80)
        else: o.append(b); return bytes(o)
src, dst, K = sys.argv[1], sys.argv[2], int(sys.argv[3])
d = open(src, 'rb').read()
assert d[:8] == b'\0asm\1\0\0\0'
p = 8; code = None
while p < len(d):
    sid = d[p]; sz, q = rleb(d, p + 1)
    if sid == 10: code = (p, q, q + sz); break
    p = q + sz
hdr, pay, end = code
n, q = rleb(d, pay)
ents = []   # (idx, start_entry, body_start, size)
for i in range(n):
    fsz, fb = rleb(d, q)
    ents.append((i, q, fb, fsz)); q = fb + fsz
sizes = sorted((e[3] for e in ents), reverse=True)
tot = sum(sizes)
print(f'funciones={n} bytes_codigo={tot}')
for lim in (1<<10, 10<<10, 100<<10, 1<<20):
    c = [s for s in sizes if s >= lim]
    print(f'  >= {lim//1024:>5} KB: {len(c):>6} funciones, {sum(c)/tot*100:5.1f}% del codigo')
print('top 25 (idx_en_Code, offset_cuerpo_hex, bytes):')
for e in sorted(ents, key=lambda e: -e[3])[:25]:
    print(f'  {e[0]:>6}  0x{e[2]:x}  {e[3]}')
if K > 0 and dst != '-':
    keep = set(e[0] for e in sorted(ents, key=lambda e: -e[3])[:K])
    STUB = wleb(3) + b'\x00\x00\x0b'
    parts = [wleb(n)] + [d[e[1]:e[2] + e[3]] if e[0] in keep else STUB for e in ents]
    newpay = b''.join(parts)
    out = d[:hdr] + bytes([10]) + wleb(len(newpay)) + newpay + d[end:]
    open(dst, 'wb').write(out)
    kb = sum(e[3] for e in ents if e[0] in keep)
    print(f'K={K}: conserva {kb} bytes ({kb/tot*100:.1f}% del codigo); wasm {len(d)} -> {len(out)}')
