import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pbedit as pb
n = bad = skip = 0
for p in sorted(glob.glob(os.path.join(sys.argv[1], '*.binarypb'))):
    b = open(p, 'rb').read(); top = pb.parse(b)
    e1, e2 = pb.first(top, 1), pb.first(top, 2)
    try:
        anyv = pb.parse(e2[2]); assert pb.first(anyv, 2) and b'TuningTreeSet' in pb.first(anyv, 1)[2]
    except Exception: skip += 1; continue
    top, uc, anyv, tts = pb.load_graph(p)
    tmp = p + '.rt'; out = pb.save_graph(tmp, top, uc, anyv, tts); os.remove(tmp); n += 1
    if out != b: bad += 1; print('DEEP FAIL', os.path.basename(p))
print('%s: graphs=%d deep-fail=%d non-graph=%d' % (os.path.basename(os.path.dirname(sys.argv[1]+'/x')), n, bad, skip))
