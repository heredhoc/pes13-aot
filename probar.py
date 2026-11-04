#!/usr/bin/env python3
"""Compila UN wasm con wamrc bajo vigilante de RAM. Uso: python3 probar.py in.wasm NOMBRE [--gdb]
Env: WAMRC, FLAGS (cadena tipo shell), LIM_KB (defecto 10 GB)"""
import os, sys, time, shlex, subprocess
wasm, name = sys.argv[1], sys.argv[2]; gdb = '--gdb' in sys.argv
WAMRC = os.environ.get('WAMRC', 'wamrc'); FLAGS = shlex.split(os.environ.get('FLAGS', ''))
LIM = int(os.environ.get('LIM_KB', str(10 * 1024 * 1024)))
cmd = ['timeout', '-k', '10', '10m', WAMRC, '--target=aarch64', '--opt-level=0'] + FLAGS + ['-o', f'{name}.aot', wasm]
print('CMD', ' '.join(shlex.quote(c) for c in cmd), flush=True)
lg = open(f'wamrc_{name}.log', 'w'); t = time.time()
p = subprocess.Popen(cmd, stdout=lg, stderr=subprocess.STDOUT)
peak = 0; blown = False; gdone = False
def rss():
    r = subprocess.run(['pgrep', '-x', 'wamrc'], capture_output=True, text=True).stdout.split()
    if not r: return None, 0
    try:
        for l in open(f'/proc/{r[0]}/status'):
            if l.startswith('VmRSS'): return r[0], int(l.split()[1])
    except OSError: pass
    return r[0], 0
while p.poll() is None:
    time.sleep(1); pid, r = rss(); peak = max(peak, r)
    if gdb and not gdone and r > 9 * 1024 * 1024:
        gdone = True
        with open(f'gdb_{name}.txt', 'w') as g:
            subprocess.run(['sudo', 'timeout', '40', 'gdb', '-p', pid, '-batch', '-ex', 'set pagination off',
                            '-ex', 'thread apply all bt 30'], stdout=g, stderr=subprocess.STDOUT)
    if r > LIM and not blown:
        blown = True; subprocess.run(['kill', '-9', pid])
size = os.path.getsize(f'{name}.aot') if os.path.exists(f'{name}.aot') else 0
line = f'RESULT {name}: {"CORTADO por RAM" if blown else "ok" if p.returncode == 0 else "rc=%s" % p.returncode} rc={p.returncode} pico={peak//1024} MB tiempo={time.time()-t:.0f}s aot={size} B'
print(line); open(f'resultado_{name}.txt', 'w').write(line + '\n' + subprocess.run(['tail', '-5', f'wamrc_{name}.log'], capture_output=True, text=True).stdout)
