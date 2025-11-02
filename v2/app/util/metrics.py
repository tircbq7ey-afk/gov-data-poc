_hist = []
def track(latency_ms: float, limit=500):
    _hist.append(latency_ms)
    if len(_hist) > limit:
        del _hist[0:len(_hist)-limit]
def p95():
    if not _hist: return 0
    s = sorted(_hist)
    idx = int(0.95 * (len(s)-1))
    return s[idx]
