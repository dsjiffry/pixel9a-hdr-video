"""Lossless protobuf wire-format editing (no schema). A message is a list of [field, wiretype, raw]."""
def _varint(b, i):
    r = s = 0
    while True:
        c = b[i]; i += 1
        r |= (c & 0x7f) << s; s += 7
        if c < 0x80: return r, i
def enc_varint(v):
    out = bytearray()
    while True:
        c = v & 0x7f; v >>= 7
        if v: out.append(c | 0x80)
        else: out.append(c); return bytes(out)
def parse(b):
    i, out = 0, []
    while i < len(b):
        key, i = _varint(b, i); f, wt = key >> 3, key & 7
        if f == 0: raise ValueError('field 0')
        if wt == 0:
            st = i; _, i = _varint(b, i); raw = b[st:i]
        elif wt == 1: raw = b[i:i+8]; i += 8
        elif wt == 5: raw = b[i:i+4]; i += 4
        elif wt == 2:
            n, i = _varint(b, i); raw = b[i:i+n]; i += n
        else: raise ValueError('wiretype %d' % wt)
        if i > len(b): raise ValueError('truncated')
        out.append([f, wt, bytes(raw)])
    return out
def serialize(msg):
    out = bytearray()
    for f, wt, raw in msg:
        out += enc_varint((f << 3) | wt)
        if wt == 2: out += enc_varint(len(raw))
        out += raw
    return bytes(out)
def get(msg, f):  return [e for e in msg if e[0] == f]
def first(msg, f):
    for e in msg:
        if e[0] == f: return e
    return None
def vint(raw): return _varint(raw, 0)[0]
def set_varint(msg, f, v):
    e = first(msg, f)
    if e is None: msg.append([f, 0, enc_varint(v)])
    else: e[1], e[2] = 0, enc_varint(v)
def replace_all(msg, f, entries):
    """Remove every occurrence of field f, insert entries (list of [f,wt,raw]) at the first old position (or end), keeping field order."""
    pos = next((k for k, e in enumerate(msg) if e[0] == f), None)
    rest = [e for e in msg if e[0] != f]
    if pos is None:
        # keep ascending field order: insert before first field number greater than f
        pos = next((k for k, e in enumerate(rest) if e[0] > f), len(rest))
    else:
        pos = sum(1 for e in msg[:pos] if e[0] != f)
    return rest[:pos] + [list(x) for x in entries] + rest[pos:]
# --- graph helpers: TuningUsecaseData{1: TuningUsecase, 2: Any{1:type_url, 2:TuningTreeSet}} ---
def load_graph(path):
    top = parse(open(path, 'rb').read())
    uc = parse(first(top, 1)[2]); anyv = parse(first(top, 2)[2]); tts = parse(first(anyv, 2)[2])
    return top, uc, anyv, tts
def save_graph(path, top, uc, anyv, tts):
    anyv = replace_all(anyv, 2, [[2, 2, serialize(tts)]])
    top = replace_all(top, 1, [[1, 2, serialize(uc)]])
    top = replace_all(top, 2, [[2, 2, serialize(anyv)]])
    data = serialize(top)
    open(path, 'wb').write(data); return data
