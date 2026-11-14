import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pbedit as pb
for p in sorted(glob.glob(os.path.join(sys.argv[1], '*.binarypb'))):
    try:
        top, uc, anyv, tts = pb.load_graph(p)
        d = {f: pb.vint(r) for f, w, r in uc if w == 0}
        print('s%-3s m%-3s u%-3s slots=%-28s %s' % (d.get(1), d.get(2), d.get(3), ','.join(str(f) for f, w, r in tts), os.path.basename(p)))
    except Exception: pass
