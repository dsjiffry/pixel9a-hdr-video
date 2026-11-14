"""Generate Pixel 9a HLG tuning graphs + patched fallback map from 9a SDR graphs and Pixel 9 Pro Fold HLG slots."""
import sys, os, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pbedit as pb
G, C, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
HLG_MAIN = (4, 7, 12, 13, 16)   # clut, gamma, ltm, ltm_delta_y, rgb_yuv_conversion
HLG_WIDE = (4, 7, 12, 16)       # Fold ultrawide HLG graphs carry no ltm_delta_y
JOBS = [  # (output, 9a base, fold donor, new usecase, slots)
 ('tegu_rear_barghest_normal_full_16_9_2160p_30fps_video_recording_bt2020_hlg', 'tegu_rear_barghest_normal_full_16_9_2160p_30fps_video_liveshot', 'comet_rear_oksoko_normal_full_16_9_2160p_30fps_video_recording_bt2020_hlg', 26, HLG_MAIN),
 ('tegu_rear_barghest_normal_full_16_9_1080p_30fps_video_recording_bt2020_hlg', 'tegu_rear_barghest_normal_full_16_9_1080p_30fps_video_liveshot', 'comet_rear_oksoko_normal_full_16_9_1080p_30fps_video_recording_bt2020_hlg', 26, HLG_MAIN),
 ('tegu_rear_leshenuw_wide_full_16_9_2160p_30fps_video_recording_bt2020_hlg', 'tegu_rear_leshenuw_wide_full_16_9_2160p_30fps_video_liveshot', 'comet_rear_imentet_wide_full_16_9_2160p_30fps_video_recording_bt2020_hlg', 26, HLG_WIDE),
 ('tegu_rear_leshenuw_wide_full_16_9_2160p_30fps_video_viewfinder_bt2020_hlg', 'tegu_rear_leshenuw_wide_full_16_9_2160p_30fps_video_viewfinder', 'comet_rear_imentet_wide_full_16_9_2160p_30fps_video_viewfinder_bt2020_hlg', 25, HLG_WIDE),
 ('tegu_rear_leshenuw_wide_full_16_9_1080p_30fps_video_recording_bt2020_hlg', 'tegu_rear_leshenuw_wide_full_16_9_1080p_30fps_video_liveshot', 'comet_rear_imentet_wide_full_16_9_1080p_30fps_video_recording_bt2020_hlg', 26, HLG_WIDE),
 # v0.3: logical (virtual) rear camera, third-party HLG viewfinder (use case 39). The Fold ships exactly this graph
 # (comet_rear_oksokorm_virtual_..._hlg_3p): its SDR viewfinder with clut replaced and gamma/ltm/rgb_yuv added.
 ('tegu_rear_barghestrm_virtual_full_4_3_full_15_30fps_video_viewfinder_bt2020_hlg_3p', 'tegu_rear_barghestrm_virtual_full_4_3_full_15_30fps_viewfinder', 'comet_rear_oksokorm_virtual_full_4_3_full_15_30fps_video_viewfinder_bt2020_hlg_3p', 39, HLG_WIDE, {4}),
]
FALLBACK_NEW = [(93, 2, 26, [25]), (93, 3, 26, [25]), (95, 3, 26, [25])]
manifest = {'graphs': [], 'fallback_added': []}
def p(d, n): return os.path.join(d, n + '.binarypb')
for out, base, donor, ucase, slots, *rest in JOBS:
    replace = rest[0] if rest else set()   # slots the base has that the donor's HLG version must overwrite
    top, uc, anyv, tts = pb.load_graph(p(G, base))
    _, _, _, dtts = pb.load_graph(p(C, donor))
    have = {f for f, w, r in tts}
    assert replace <= have, (out, 'replace slots missing from base', replace - have)
    clash = [f for f in slots if f in have and f not in replace]
    assert not clash, (out, 'base already has slots', clash)
    for f in slots:
        src = pb.get(dtts, f); assert src, (donor, 'donor lacks slot', f)
        tts = pb.replace_all(tts, f, src)
    pb.set_varint(uc, 3, ucase)
    data = pb.save_graph(p(OUT, out), top, uc, anyv, tts)
    hdr = {f: pb.vint(r) for f, w, r in uc if w == 0}
    manifest['graphs'].append({'file': out + '.binarypb', 'sensor': hdr[1], 'mode': hdr[2], 'usecase': hdr[3],
        'base': base, 'donor': donor, 'slots_added': list(slots), 'sha256': hashlib.sha256(data).hexdigest()})
# --- fallback map ---
fb = pb.parse(open(p(G, 'tegu_fallback_map'), 'rb').read())
def key(raw):
    d = {f: pb.vint(r) for f, w, r in pb.parse(raw) if w == 0}; return (d.get(1, 0), d.get(2, 0), d.get(3, 0))
def tu(s, m, u): return pb.serialize([[1, 0, pb.enc_varint(s)], [2, 0, pb.enc_varint(m)], [3, 0, pb.enc_varint(u)]])
existing = {key(pb.first(pb.parse(r), 1)[2]) for f, w, r in fb}
entries = [e for e in fb]
for s, m, u, sup in FALLBACK_NEW:
    assert (s, m, u) not in existing
    entry = pb.serialize([[1, 2, tu(s, m, u)]] + [[2, 2, tu(s, m, x)] for x in sup])
    # keep the map sorted by canonical (sensor, mode, usecase)
    pos = next((k for k, e in enumerate(entries) if key(pb.first(pb.parse(e[2]), 1)[2]) > (s, m, u)), len(entries))
    entries.insert(pos, [1, 2, entry])
    manifest['fallback_added'].append({'canonical': [s, m, u], 'supported': [[s, m, x] for x in sup]})
data = pb.serialize(entries)
open(p(OUT, 'tegu_fallback_map'), 'wb').write(data)
manifest['fallback_sha256'] = hashlib.sha256(data).hexdigest()
json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1)
print(json.dumps(manifest, indent=1))
