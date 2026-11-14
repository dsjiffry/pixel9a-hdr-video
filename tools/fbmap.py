import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pbedit as pb
def uc(raw):
    d = {f: pb.vint(r) for f, w, r in pb.parse(raw) if w == 0}
    return '(s%s m%s u%s)' % (d.get(1), d.get(2), d.get(3))
top = pb.parse(open(sys.argv[1], 'rb').read())
filt = set(int(x) for x in sys.argv[2].split(',')) if len(sys.argv) > 2 else None
for k, (f, wt, raw) in enumerate(top):
    e = pb.parse(raw)
    can = uc(pb.first(e, 1)[2]); sup = [uc(r) for ff, w, r in e if ff == 2]; bak = [uc(r) for ff, w, r in e if ff == 3]
    if filt and not any(('u%d)' % x) in s for s in [can] + sup + bak for x in filt): continue
    print('#%d canonical=%s backup=%s supported=%s' % (k, can, bak, sup))
