#!/usr/bin/env python3
"""FAA NASR(28일 주기, 무료) CSV → route.html이 쓰는 작은 항법 데이터(navdata/*.json)
- 픽스·VOR/NDB·공항 좌표, 항로(J/Q/V/T…), SID(DP)·STAR 경로
- GitHub Actions(.github/workflows/navdata.yml)가 28일마다 실행해서 저장소에 올림
"""
import csv, io, json, os, sys, urllib.request, zipfile, datetime

BASE = datetime.date(2026, 10, 29)   # 알려진 NASR 주기 시작일 (28일씩)
OUT = sys.argv[1] if len(sys.argv) > 1 else 'navdata'

def cycle(today=None):
    today = today or datetime.datetime.utcnow().date()
    n = (today - BASE).days // 28
    return BASE + datetime.timedelta(days=28 * n)

def get_zip(name, day):
    tag = day.strftime('%d_%b_%Y')
    url = f'https://nfdc.faa.gov/webContent/28DaySub/extra/{tag}_{name}_CSV.zip'
    req = urllib.request.Request(url, headers={'User-Agent': 'KAPA navdata builder (github actions)'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return zipfile.ZipFile(io.BytesIO(r.read())), url

def rows(z, want):
    """zip 안에서 이름에 want가 들어간 CSV를 찾아 dict 행으로"""
    names = [n for n in z.namelist() if n.upper().endswith('.CSV') and want.upper() in os.path.basename(n).upper()]
    if not names:
        return [], None, []
    name = sorted(names, key=len)[0]
    with z.open(name) as f:
        rd = csv.DictReader(io.TextIOWrapper(f, encoding='latin-1', newline=''))
        hdr = rd.fieldnames or []
        return list(rd), name, hdr

def col(hdr, *cands):
    H = {h.strip().upper(): h for h in hdr}
    for c in cands:
        if c in H: return H[c]
    for c in cands:
        for k, v in H.items():
            if c in k: return v
    return None

def num(x):
    try: return round(float(x), 5)
    except Exception: return None

log = []
def note(*a):
    s = ' '.join(str(x) for x in a); print(s); log.append(s)

def main():
    day = cycle()
    note('cycle', day.isoformat())
    try:   # 같은 주기로 이미 만들었으면 건너뜀 (수동 실행은 FORCE=1)
        old = json.load(open(os.path.join(OUT, 'points.json')))['meta']['cycle']
        if old == day.isoformat() and os.environ.get('FORCE') != '1':
            note('already built for this cycle'); return
    except Exception: pass
    pts = {}   # 이름 → [[lat, lon, kind], ...] (같은 이름이 여러 곳이면 여러 개)
    def add(name, lat, lon, kind):
        name = (name or '').strip().upper()
        if not name or lat is None or lon is None: return
        lst = pts.setdefault(name, [])
        if not any(abs(p[0] - lat) < 1e-3 and abs(p[1] - lon) < 1e-3 for p in lst):
            lst.append([lat, lon, kind])

    # 픽스
    z, url = get_zip('FIX', day); note('FIX', url)
    rs, nm, hdr = rows(z, 'FIX_BASE'); note('  ', nm, hdr[:20])
    cid, cla, clo = col(hdr, 'FIX_ID'), col(hdr, 'LAT_DECIMAL'), col(hdr, 'LONG_DECIMAL', 'LON_DECIMAL')
    for r in rs: add(r[cid], num(r[cla]), num(r[clo]), 'F')
    note('  fixes', len(rs))
    # VOR/NDB
    z, url = get_zip('NAV', day); note('NAV', url)
    rs, nm, hdr = rows(z, 'NAV_BASE'); note('  ', nm, hdr[:20])
    cid, cty, cla, clo = col(hdr, 'NAV_ID'), col(hdr, 'NAV_TYPE'), col(hdr, 'LAT_DECIMAL'), col(hdr, 'LONG_DECIMAL', 'LON_DECIMAL')
    for r in rs: add(r[cid], num(r[cla]), num(r[clo]), 'N')
    note('  navaids', len(rs))
    # 공항 (FAA 3글자 + ICAO 둘 다)
    z, url = get_zip('APT', day); note('APT', url)
    rs, nm, hdr = rows(z, 'APT_BASE'); note('  ', nm, hdr[:24])
    cid, cic, cla, clo = col(hdr, 'ARPT_ID'), col(hdr, 'ICAO_ID'), col(hdr, 'LAT_DECIMAL'), col(hdr, 'LONG_DECIMAL', 'LON_DECIMAL')
    napt = 0
    for r in rs:
        if not r.get(cic): continue   # ICAO 코드가 있는 공항만 (작은 비행장 제외)
        la, lo = num(r[cla]), num(r[clo])
        add(r[cic], la, lo, 'A'); add(r[cid], la, lo, 'A'); napt += 1
    note('  airports', napt)

    # 항로: AWY_BASE의 AIRWAY_STRING(점 순서)
    awy = {}
    z, url = get_zip('AWY', day); note('AWY', url)
    rs, nm, hdr = rows(z, 'AWY_BASE'); note('  ', nm, hdr[:20])
    cid, cst, cloc = col(hdr, 'AWY_ID'), col(hdr, 'AIRWAY_STRING'), col(hdr, 'AWY_LOCATION')
    if cst:
        for r in rs:
            k = r[cid].strip().upper(); seq = r[cst].split()
            if k and seq: awy.setdefault(k, []).append(seq)
    else:
        rs, nm, hdr = rows(z, 'AWY_SEG'); note('  fallback', nm, hdr[:20])
        cid, cseq, cfrom = col(hdr, 'AWY_ID'), col(hdr, 'POINT_SEQ', 'SEQ'), col(hdr, 'FROM_POINT', 'POINT')
        tmp = {}
        for r in rs: tmp.setdefault(r[cid].strip().upper(), []).append((int(float(r[cseq] or 0)), r[cfrom].strip().upper()))
        for k, v in tmp.items(): awy.setdefault(k, []).append([p for _, p in sorted(v)])
    note('  airways', len(awy))

    # SID(DP) / STAR: 절차 이름 → {transition: [점들]} (BODY는 '*')
    procs = {}
    for kind, zname, base in (('DP', 'DP', 'DP_RTE'), ('STAR', 'STAR', 'STAR_RTE')):
        z, url = get_zip(zname, day); note(kind, url)
        rs, nm, hdr = rows(z, base); note('  ', nm, hdr[:24])
        ccode = col(hdr, kind + '_COMPUTER_CODE', 'COMPUTER_CODE')
        cport = col(hdr, 'ROUTE_PORTION_TYPE', 'PORTION')
        cname = col(hdr, 'ROUTE_NAME', 'TRANSITION_COMPUTER_CODE')
        cbody = col(hdr, 'BODY_SEQ')
        cseq, cpt = col(hdr, 'POINT_SEQ'), col(hdr, 'POINT')
        grp = {}
        for r in rs:
            code = (r.get(ccode) or '').strip().upper()
            proc = code.split('.')[0] if kind == 'DP' else (code.split('.')[-1] if '.' in code else code)
            if not proc: continue
            port = (r.get(cport) or '').upper()
            tname = '*' if 'BODY' in port else (r.get(cname) or '').strip().upper()
            key = (proc, tname, r.get(cbody) or '')
            try: s = int(float(r.get(cseq) or 0))
            except Exception: s = 0
            grp.setdefault(key, []).append((s, (r.get(cpt) or '').strip().upper()))
        for (proc, tname, body), v in grp.items():
            seq = [p for _, p in sorted(v) if p]
            d = procs.setdefault(proc, {'k': kind, 't': {}})
            d['t'].setdefault(tname, []).append(seq)
        note('  procedures', sum(1 for p in procs.values() if p['k'] == kind))

    os.makedirs(OUT, exist_ok=True)
    # 좌표는 4자리로 줄이고, 한 곳뿐이면 [lat, lon]
    P = {k: ([round(v[0][0], 4), round(v[0][1], 4)] if len(v) == 1 else [[round(a, 4), round(b, 4)] for a, b, _ in v]) for k, v in pts.items()}
    meta = {'cycle': day.isoformat(), 'source': 'FAA NASR 28-day subscription (CSV)', 'built': datetime.datetime.utcnow().isoformat() + 'Z'}
    with open(os.path.join(OUT, 'points.json'), 'w') as f: json.dump({'meta': meta, 'p': P}, f, separators=(',', ':'))
    with open(os.path.join(OUT, 'routes.json'), 'w') as f: json.dump({'meta': meta, 'awy': awy, 'proc': procs}, f, separators=(',', ':'))
    with open(os.path.join(OUT, 'build-log.txt'), 'w') as f: f.write('\n'.join(log) + '\n')
    note('points', len(P), 'airways', len(awy), 'procs', len(procs))

if __name__ == '__main__':
    main()
