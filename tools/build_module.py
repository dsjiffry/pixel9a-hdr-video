"""Package ../module into an installable KernelSU zip after checking line endings, script syntax inputs and payload hashes.
Usage: python -I tools/build_module.py
"""
import hashlib, os, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, 'module')
OUT = os.path.join(ROOT, 'dist')
SCRIPTS = {'service.sh', 'action.sh', 'customize.sh', 'common.sh'}

def fail(msg):
    sys.exit('BUILD FAILED: ' + msg)

props = dict(l.split('=', 1) for l in open(os.path.join(MOD, 'module.prop'), encoding='ascii').read().splitlines() if '=' in l)
for k in ('id', 'name', 'version', 'versionCode', 'author', 'description'):
    if k not in props: fail('module.prop missing ' + k)

# Text files must use LF only, or /system/bin/sh will choke on \r.
for dp, _, fs in os.walk(MOD):
    for f in fs:
        if f.endswith(('.sh', '.prop')) or f == 'SHA256SUMS':
            if b'\r' in open(os.path.join(dp, f), 'rb').read(): fail('CRLF line endings in ' + f)

# Payload must match its checksum list exactly (same list the phone verifies at boot).
pdir = os.path.join(MOD, 'camera_hlg')
listed = {}
for line in open(os.path.join(pdir, 'SHA256SUMS'), encoding='ascii'):
    h, name = line.split()
    listed[name] = h
actual = {f for f in os.listdir(pdir) if f.endswith('.binarypb')}
if set(listed) != actual: fail('SHA256SUMS does not list exactly the payload files')
for name, h in listed.items():
    if hashlib.sha256(open(os.path.join(pdir, name), 'rb').read()).hexdigest() != h: fail('hash mismatch ' + name)

os.makedirs(OUT, exist_ok=True)
zpath = os.path.join(OUT, '%s-%s.zip' % (props['id'], props['version']))
with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
    for dp, _, fs in os.walk(MOD):
        for f in sorted(fs):
            full = os.path.join(dp, f)
            arc = os.path.relpath(full, MOD).replace(os.sep, '/')
            if arc == 'hdr.log': continue
            zi = zipfile.ZipInfo(arc, date_time=(2026, 11, 13, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = ((0o755 if f in SCRIPTS else 0o644) | 0o100000) << 16
            z.writestr(zi, open(full, 'rb').read())
print('built', zpath, os.path.getsize(zpath), 'bytes')
print('sha256', hashlib.sha256(open(zpath, 'rb').read()).hexdigest())
