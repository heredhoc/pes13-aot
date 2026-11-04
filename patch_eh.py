#!/usr/bin/env python3
"""Quita el unico try/catch_all/rethrow de PES13 (func 'dispatch').
Uso: python3 patch_eh.py entrada.wasm salida.wasm
Deja solo el cuerpo del try (run_target + host_call). Se pierde el camino
catch_all -> host_unwound (desenrollado por excepcion del host)."""
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

src, dst = sys.argv[1], sys.argv[2]
d = open(src, 'rb').read()
assert d[:8] == b'\0asm\1\0\0\0', 'cabecera wasm invalida'
PAT = bytes.fromhex('0640200020011 0aa0145044020 0020012000280210'.replace(' ', ''))
PAT = bytes.fromhex('06402000200110aa01450440')
hits = []
i = d.find(PAT)
while i >= 0:
    hits.append(i); i = d.find(PAT, i + 1)
assert len(hits) == 1, f'patron try/run_target: {len(hits)} apariciones (se esperaba 1)'
hit = hits[0]
# recorrer secciones hasta Code (id 10)
p = 8; code = None
while p < len(d):
    sid = d[p]; sz, q = rleb(d, p + 1)
    if sid == 10: code = (p, q, q + sz); break
    p = q + sz
assert code, 'sin seccion Code'
sec_hdr, sec_pay, sec_end = code
n, q = rleb(d, sec_pay)
for _ in range(n):
    fsz, fb = rleb(d, q)
    if fb <= hit < fb + fsz: break
    q = fb + fsz
else:
    raise SystemExit('no se encontro la funcion que contiene el patron')
ent_start, body, body_end = q, fb, fb + fsz
B = d[body:body_end]
t = hit - body
c = B.find(b'\x19', t)           # catch_all
assert B[t:t+2] == b'\x06\x40'
# fin del try: ultimo 'end' antes del cierre de funcion: esperamos ... 09 01 0b 0b | resto
e = B.find(bytes.fromhex('09010b0b'), c)
assert e > 0, 'no se encontro rethrow 1 / end / end'
e += 3                           # posicion del 'end' del try
assert B[e] == 0x0b
assert B.count(b'\x06\x40') >= 1
new = B[:t] + B[t+2:c] + B[e+1:]
print(f'funcion en 0x{body:x}, cuerpo {len(B)} -> {len(new)} bytes')
print('quitado:', B[t:t+2].hex(), '...', B[c:e+1].hex())
ent = wleb(len(new)) + new
delta = len(ent) - (body_end - ent_start)
sec_new_pay = d[sec_pay:ent_start] + ent + d[body_end:sec_end]
out = d[:sec_hdr] + bytes([10]) + wleb(len(sec_new_pay)) + sec_new_pay + d[sec_end:]
open(dst, 'wb').write(out)
print(f'ok: {src} {len(d)} -> {dst} {len(out)} (delta {len(out)-len(d)})')
