import sys, os, glob, hashlib, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pbedit as pb
NAMES = {1:'blc',2:'byr_dns',3:'ccm',4:'clut',5:'dmsc',6:'dpc',7:'gamma',8:'green_imbalance',9:'gtnr',10:'gtnr_sharpener',11:'hlr',12:'ltm',13:'ltm_delta_y',14:'lsc',15:'lsc_stats',16:'rgb_yuv_conversion',17:'rgbp_gtm',19:'sobek',20:'wb',21:'yuv_nr',22:'yuv_sharp_enhancer',23:'hf_decomp',24:'refine_lme',25:'linearization',26:'gatmv2',27:'hf_recomp',28:'gtnr_segmentation',29:'ilk60',30:'sw_post_sharpen',31:'dsnr',32:'compute_global_motion',33:'hdrnet',34:'ml_aligner'}
def slots(path):
    top, uc, anyv, tts = pb.load_graph(path)
    d = {}
    for f, wt, raw in tts: d.setdefault(f, []).append(raw)
    return {f: hashlib.sha1(b''.join(v)).hexdigest()[:8] + ':%d' % sum(map(len, v)) for f, v in d.items()}, uc
if sys.argv[1] == 'deeprt':
    bad = 0
    for p in glob.glob(os.path.join(sys.argv[2], '*_*fps_*.binarypb')):
        b = open(p, 'rb').read(); top, uc, anyv, tts = pb.load_graph(p)
        tmp = tempfile.mktemp(); out = pb.save_graph(tmp, top, uc, anyv, tts); os.remove(tmp)
        if out != b: bad += 1; print('DEEP FAIL', os.path.basename(p))
    print('deep round-trip failures:', bad); sys.exit()
a, b = sys.argv[1], sys.argv[2]
sa, ua = slots(a); sb, ub = slots(b)
print('A usecase', [(f, pb.vint(r)) for f, w, r in ua if w == 0], os.path.basename(a))
print('B usecase', [(f, pb.vint(r)) for f, w, r in ub if w == 0], os.path.basename(b))
for f in sorted(set(sa) | set(sb)):
    x, y = sa.get(f, '-'), sb.get(f, '-')
    tag = 'same' if x == y else ('ADDED' if x == '-' else ('REMOVED' if y == '-' else 'CHANGED'))
    print('%3d %-22s %-8s A=%s B=%s' % (f, NAMES.get(f, '?'), tag, x, y))
