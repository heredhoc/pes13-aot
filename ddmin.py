#!/usr/bin/env python3
"""Delta debugging: halla el conjunto minimo de funciones de una banda que dispara la RAM de wamrc.
Uso: python3 ddmin.py in.wasm LO HI     (banda LO-HI % de la muestra; contexto base = 0-LO %)
Env: WAMRC (ruta), WAMRC_FLAGS (flags extra), LIM_KB (corte, defecto 10 GB), BUDGET_MIN (defecto 120)"""
import os, sys, time, json, shlex, shutil, subprocess
import band
src, LO, HI = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
WAMRC = os.environ.get('WAMRC', 'wamrc')
FLAGS = shlex.split(os.environ.get('WAMRC_FLAGS', ''))
LIM = int(os.environ.get('LIM_KB', str(10 * 1024 * 1024)))
BUDGET = float(os.environ.get('BUDGET_MIN', '120')) * 60
T0 = time.time()
d, secs, (hdr, pay, end), funcs = band.load(src)
nm = band.names(d, secs, band.nimports(d, secs))
STUB = band.wleb(3) + b'\x00\x00\x0b'
base_ids = [i for i in range(len(funcs)) if band.bucket(i) < LO * 10]
cands0 = band.band(funcs, LO, HI)
ntest = 0
best = None
def log(m):
    print(f'[{(time.time()-T0)/60:5.1f} min] {m}', flush=True)
    open('bisect.log', 'a').write(f'[{(time.time()-T0)/60:5.1f} min] {m}\n')
def build(keep, out):
    ks = set(keep)
    parts = [band.wleb(len(funcs))]
    for i, (s, e, fsz, nl) in enumerate(funcs):
        parts.append(d[s:e] if i in ks else STUB)
    newpay = b''.join(parts)
    open(out, 'wb').write(d[:hdr] + bytes([10]) + band.wleb(len(newpay)) + newpay + d[end:])
def rss_of_wamrc():
    r = subprocess.run(['pgrep', '-x', 'wamrc'], capture_output=True, text=True).stdout.split()
    if not r: return None, 0
    pid = r[0]
    try:
        for l in open(f'/proc/{pid}/status'):
            if l.startswith('VmRSS'): return pid, int(l.split()[1])
    except OSError: pass
    return pid, 0
def run(wasm, tag, gdb=False):
    cmd = []
    if shutil.which('time') or os.path.exists('/usr/bin/time'):
        cmd += ['/usr/bin/time', '-v', '-o', f'time_{tag}.txt']
    cmd += ['timeout', '-k', '10', '12m', WAMRC, '--target=aarch64', '--opt-level=0'] + FLAGS + ['-o', 't.aot', wasm]
    lg = open(f'wamrc_{tag}.log', 'w')
    t = time.time(); p = subprocess.Popen(cmd, stdout=lg, stderr=subprocess.STDOUT)
    peak = 0; blown = False; gdone = False
    while p.poll() is None:
        time.sleep(1)
        pid, rss = rss_of_wamrc()
        peak = max(peak, rss)
        if gdb and not gdone and rss > 9 * 1024 * 1024:
            gdone = True
            with open('gdb_final.txt', 'w') as g:
                subprocess.run(['sudo', 'timeout', '40', 'gdb', '-p', pid, '-batch', '-ex', 'set pagination off',
                                '-ex', 'thread apply all bt 25'], stdout=g, stderr=subprocess.STDOUT)
        if rss > LIM and not blown:
            blown = True
            subprocess.run(['kill', '-9', pid])
    rc = p.returncode
    return blown, rc, peak, time.time() - t
def fails(subset, ctx=True):
    """True = el subconjunto dispara la RAM."""
    global ntest, best
    if time.time() - T0 > BUDGET: raise TimeoutError
    ntest += 1
    keep = (base_ids if ctx else []) + list(subset)
    build(keep, 'cur.wasm')
    blown, rc, peak, el = run('cur.wasm', 'cur')
    if not blown and rc not in (0,):
        log(f'test {ntest}: {len(subset)} funcs rc={rc} (ni RAM ni OK; se trata como NO falla)')
    log(f'test {ntest}: {len(subset)} funcs ctx={ctx} -> {"FALLA (RAM)" if blown else "ok"} pico={peak//1024} MB {el:.0f}s')
    if blown and (best is None or len(subset) < len(best)):
        best = list(subset)
        json.dump({'ids': best}, open('best.json', 'w'))
    return blown
def ddmin(c):
    n = 2
    while len(c) >= 2:
        sz = (len(c) + n - 1) // n
        chunks = [c[i:i + sz] for i in range(0, len(c), sz)]
        done = False
        for ch in chunks:
            if fails(ch, CTX): c = ch; n = 2; done = True; break
        if not done and n > 2:
            for ch in chunks:
                s = set(ch); comp = [x for x in c if x not in s]
                if comp and fails(comp, CTX): c = comp; n = max(n - 1, 2); done = True; break
        if not done:
            if n >= len(c): break
            n = min(len(c), n * 2)
    return c
log(f'banda {LO}-{HI} %: {len(cands0)} funciones; contexto base 0-{LO} %: {len(base_ids)} funciones')
CTX = True
try:
    if not fails(cands0, True):
        log('con la banda completa y contexto NO falla: no se reproduce; se detiene'); sys.exit(0)
    if fails(cands0, False):
        CTX = False; log('la banda sola (sin contexto) tambien falla: sigo SIN contexto (mas rapido)')
    else:
        log('la banda sola NO falla: sigo CON contexto 0-%s %%' % LO)
    res = ddmin(cands0)
    done = True
except TimeoutError:
    res = best or cands0; done = False
    log('presupuesto de tiempo agotado: reporto el mejor conjunto que falla hallado')
with open('result.txt', 'w') as f:
    f.write(f'completo={done} ctx={CTX} tests={ntest} funciones_que_fallan={len(res)}\n')
    for i in res:
        f.write(f'idx={i} bytes={funcs[i][2]} locales={funcs[i][3]} bucket={band.bucket(i)} nombre={nm.get(i, "-")}\n')
    if done and len(res) <= 5:
        build((base_ids if CTX else []) + list(res), 'final.wasm')
        blown, rc, peak, el = run('final.wasm', 'final', gdb=True)
        f.write(f'confirmacion con gdb: blown={blown} rc={rc} pico={peak//1024} MB\n')
log(open('result.txt').read())
