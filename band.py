#!/usr/bin/env python3
"""Aisla funciones problematicas entre dos muestras anidadas de trim_wasm.py.
Funcion i esta en la muestra PCT si (i*2654435761)%1000 < PCT*10.
Uso:
  python3 band.py info  in.wasm [BASE_PCT BAND_PCT]          (defecto 24 28; lista las mayores de la banda)
  python3 band.py trim  in.wasm out.wasm BASE_PCT BAND_PCT top:N|notop:N
     top:N   = base + SOLO las N funciones mas grandes de la banda
     notop:N = base + toda la banda MENOS las N mas grandes
  python3 band.py only in.wasm out.wasm IDX     (solo esa funcion; imprime su cuerpo en hex)
  python3 band.py ranges in.wasm out.wasm "0-24,28-32"     (conserva funciones con bucket en esos rangos de %)"""
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
def sections(d):
    p = 8
    while p < len(d):
        sid = d[p]; sz, q = rleb(d, p + 1)
        yield sid, p, q, q + sz
        p = q + sz
def load(path):
    d = open(path, 'rb').read()
    assert d[:8] == b'\0asm\1\0\0\0'
    secs = list(sections(d))
    code = [s for s in secs if s[0] == 10][0]
    hdr, pay, end = code[1], code[2], code[3]
    n, q = rleb(d, pay)
    funcs = []   # (inicio_entrada, fin_entrada, tam_cuerpo, locales)
    for i in range(n):
        fsz, fb = rleb(d, q)
        nl, r = rleb(d, fb); tot = 0
        for _ in range(nl):
            c, r = rleb(d, r); r += 1; tot += c
        funcs.append((q, fb + fsz, fsz, tot))
        q = fb + fsz
    return d, secs, (hdr, pay, end), funcs
def nimports(d, secs):
    c = 0
    for sid, st, a, b in secs:
        if sid != 2: continue
        n, p = rleb(d, a)
        for _ in range(n):
            l, p = rleb(d, p); p += l
            l, p = rleb(d, p); p += l
            k = d[p]; p += 1
            if k == 0: c += 1; _, p = rleb(d, p)
            elif k == 1:
                p += 1; fl = d[p]; p += 1; _, p = rleb(d, p)
                if fl & 1: _, p = rleb(d, p)
            elif k == 2:
                fl = d[p]; p += 1; _, p = rleb(d, p)
                if fl & 1: _, p = rleb(d, p)
            elif k == 3: p += 2
            elif k == 4: p += 1; _, p = rleb(d, p)
    return c
def names(d, secs, nimp):
    out = {}
    try:
        for sid, st, a, b in secs:
            if sid != 0: continue
            l, p = rleb(d, a)
            if d[p:p + l] != b'name': continue
            p += l
            while p < b:
                sub = d[p]; sl, p2 = rleb(d, p + 1); e = p2 + sl
                if sub == 1:
                    n, r = rleb(d, p2)
                    for _ in range(n):
                        idx, r = rleb(d, r); ln, r = rleb(d, r)
                        out[idx - nimp] = d[r:r + ln].decode('utf8', 'replace'); r += ln
                p = e
    except Exception as ex:
        print('(sin nombres:', ex, ')')
    return out
def bucket(i): return (i * 2654435761) % 1000
def band(funcs, base, hi):
    return [i for i in range(len(funcs)) if base * 10 <= bucket(i) < hi * 10]
def main():
    if sys.argv[1] == 'info':
        d, secs, code, funcs = load(sys.argv[2])
        base = float(sys.argv[3]) if len(sys.argv) > 3 else 24
        hi = float(sys.argv[4]) if len(sys.argv) > 4 else 28
        nm = names(d, secs, nimports(d, secs))
        print(f'funciones: {len(funcs)}; con nombre: {len(nm)}')
        print('--- 25 funciones mas grandes de TODO el wasm (idx, bytes, locales, bucket, nombre)')
        for i in sorted(range(len(funcs)), key=lambda i: -funcs[i][2])[:25]:
            print(i, funcs[i][2], funcs[i][3], bucket(i), nm.get(i, '-'))
        bd = band(funcs, base, hi)
        print(f'--- banda {base}-{hi} %: {len(bd)} funciones, {sum(funcs[i][2] for i in bd)} bytes; las 25 mas grandes')
        for i in sorted(bd, key=lambda i: -funcs[i][2])[:25]:
            print(i, funcs[i][2], funcs[i][3], bucket(i), nm.get(i, '-'))
        print('--- por franja de 4 %: funciones, bytes, mayor funcion')
        for lo in range(0, 100, 4):
            ids = band(funcs, lo, lo + 4)
            if ids: print(f'{lo}-{lo+4}: {len(ids)} {sum(funcs[i][2] for i in ids)} max={max(funcs[i][2] for i in ids)}')
    elif sys.argv[1] == 'only':
        d, secs, (hdr, pay, end), funcs = load(sys.argv[2])
        k = int(sys.argv[4])
        STUB = wleb(3) + b'\x00\x00\x0b'
        parts = [wleb(len(funcs))] + [d[a:b] if i == k else STUB for i, (a, b, fsz, nl) in enumerate(funcs)]
        newpay = b''.join(parts)
        open(sys.argv[3], 'wb').write(d[:hdr] + bytes([10]) + wleb(len(newpay)) + newpay + d[end:])
        a, b, fsz, nl = funcs[k]
        print(f'idx {k}: {fsz} bytes de cuerpo, {nl} locales; hex del cuerpo:')
        body = d[a:b]
        for o in range(0, len(body), 32): print(body[o:o+32].hex(' '))
    elif sys.argv[1] == 'ranges':
        d, secs, (hdr, pay, end), funcs = load(sys.argv[2])
        rg = [tuple(float(x) for x in r.split('-')) for r in sys.argv[4].split(',')]
        STUB = wleb(3) + b'\x00\x00\x0b'
        parts = [wleb(len(funcs))]; kept = kb = 0
        for i, (s_, e, fsz, nl) in enumerate(funcs):
            k = any(lo * 10 <= bucket(i) < hi * 10 for lo, hi in rg)
            parts.append(d[s_:e] if k else STUB); kept += k; kb += fsz if k else 0
        newpay = b''.join(parts)
        open(sys.argv[3], 'wb').write(d[:hdr] + bytes([10]) + wleb(len(newpay)) + newpay + d[end:])
        print(f'rangos {sys.argv[4]}: funciones {kept}/{len(funcs)}, bytes de codigo {kb}')
    else:
        d, secs, (hdr, pay, end), funcs = load(sys.argv[2])
        dst, base, hi, mode = sys.argv[3], float(sys.argv[4]), float(sys.argv[5]), sys.argv[6]
        kind, n = mode.split(':'); n = int(n)
        bd = band(funcs, base, hi)
        big = set(sorted(bd, key=lambda i: -funcs[i][2])[:n])
        STUB = wleb(3) + b'\x00\x00\x0b'
        parts = [wleb(len(funcs))]; kept = 0
        for i, (s, e, fsz, nl) in enumerate(funcs):
            inbase = bucket(i) < base * 10
            inband = base * 10 <= bucket(i) < hi * 10
            keep = inbase or (inband and ((i in big) if kind == 'top' else (i not in big)))
            parts.append(d[s:e] if keep else STUB); kept += keep
        newpay = b''.join(parts)
        open(dst, 'wb').write(d[:hdr] + bytes([10]) + wleb(len(newpay)) + newpay + d[end:])
        print(f'{mode} base={base} banda={hi}: funciones {kept}/{len(funcs)}; grandes aislados: {sorted(big)}')

if __name__ == '__main__':
    main()
