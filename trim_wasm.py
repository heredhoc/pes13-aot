#!/usr/bin/env python3
"""Vacia (unreachable) la mayoria de cuerpos de funcion; conserva ~PCT% (muestra pseudoaleatoria fija).
Uso: python3 trim_wasm.py entrada.wasm salida.wasm PCT   (PCT puede ser 2, 4.5, ...)"""
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
src, dst, pct = sys.argv[1], sys.argv[2], float(sys.argv[3])
d = open(src, 'rb').read()
assert d[:8] == b'\0asm\1\0\0\0'
p = 8; code = None
while p < len(d):
    sid = d[p]; sz, q = rleb(d, p + 1)
    if sid == 10: code = (p, q, q + sz); break
    p = q + sz
assert code, 'sin seccion Code'
hdr, pay, end = code
n, q = rleb(d, pay)
parts = [wleb(n)]
STUB = wleb(3) + b'\x00\x00\x0b'   # 0 locals, unreachable, end
keep_n = keep_b = tot_b = 0
thr = int(pct * 10)               # sobre 1000
for i in range(n):
    fsz, fb = rleb(d, q)
    ent = d[q:fb + fsz]
    tot_b += fsz
    if (i * 2654435761) % 1000 < thr:
        parts.append(ent); keep_n += 1; keep_b += fsz
    else:
        parts.append(STUB)
    q = fb + fsz
newpay = b''.join(parts)
out = d[:hdr] + bytes([10]) + wleb(len(newpay)) + newpay + d[end:]
open(dst, 'wb').write(out)
print(f'pct={pct}: funciones {keep_n}/{n} ({100*keep_n/n:.1f}%), bytes de codigo {keep_b}/{tot_b} ({100*keep_b/tot_b:.1f}%), wasm {len(d)} -> {len(out)}')
