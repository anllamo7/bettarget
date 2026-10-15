"""Descarga datos gratuitos de football-data.co.uk (sin clave), calcula probabilidades
con los últimos partidos de cada equipo y escribe data.json para los próximos 3 días."""
import csv, difflib, io, json, math, os, re, time, unicodedata, urllib.request, datetime as dt
BASE = 'https://www.football-data.co.uk/'
LG = {'SP1': 'LaLiga', 'SP2': 'LaLiga 2', 'E0': 'Premier League', 'E1': 'Championship', 'E2': 'League One', 'I1': 'Serie A', 'I2': 'Serie B',
      'D1': 'Bundesliga', 'D2': '2. Bundesliga', 'F1': 'Ligue 1', 'F2': 'Ligue 2', 'N1': 'Eredivisie', 'P1': 'Primeira Liga',
      'B1': 'Pro League', 'T1': 'Süper Lig', 'SC0': 'Premiership', 'G1': 'Super League'}
PH = {'c': 1.4, 'y': 1.25, 's': 1.3, 't': 1.2}
NM = {'c': 'Córners totales', 'y': 'Tarjetas totales', 's': 'Remates totales', 't': 'Remates a puerta totales'}
NMT = {'c': 'Córners de equipo', 'y': 'Tarjetas de equipo', 's': 'Remates de equipo', 't': 'Remates a puerta de equipo'}
MOST = {'c': 'Más córners', 'y': 'Más tarjetas', 's': 'Más remates', 't': 'Más remates a puerta'}

def get(path):
    rq = urllib.request.Request(BASE + path, headers={'User-Agent': 'Mozilla/5.0'})
    return urllib.request.urlopen(rq, timeout=40).read().decode('utf-8-sig', 'ignore')

def rows(t):
    return [{(k or '').strip(): (v or '').strip() for k, v in r.items()} for r in csv.DictReader(io.StringIO(t))]

def pdate(s):
    d, m, y = s.split('/'); y = int(y); y += 2000 if y < 100 else 0
    return dt.date(y, int(m), int(d))

def n(x):
    try: return float(x)
    except Exception: return float('nan')

def V(x):
    return {'g': (n(x.get('FTHG')), n(x.get('FTAG'))), 'c': (n(x.get('HC')), n(x.get('AC'))),
            'y': (n(x.get('HY')) + n(x.get('HR') or 0), n(x.get('AY')) + n(x.get('AR') or 0)),
            's': (n(x.get('HS')), n(x.get('AS'))), 't': (n(x.get('HST')), n(x.get('AST')))}

def form(hist, t):
    m = [x for x in hist if t in (x['HomeTeam'], x['AwayTeam'])][-8:]
    if len(m) < 5: return None
    o = {}
    for k in 'gcyst':
        s = [0, 0]; c = 0
        for x in m:
            v = V(x)[k]
            if math.isnan(v[0] + v[1]): continue
            h = x['HomeTeam'] == t
            s[0] += v[0] if h else v[1]; s[1] += v[1] if h else v[0]; c += 1
        o[k] = (s[0] / c, s[1] / c, c) if c >= 4 else None
    return o

def lgavg(hist):
    o = {}
    for k in 'gcyst':
        v = [(a + b) / 2 for a, b in (V(x)[k] for x in hist) if not math.isnan(a + b)]
        o[k] = sum(v) / len(v) if v else 0
    return o

def pois(k, l): return math.exp(-l) * l ** k / math.factorial(k)
def Phi(x): return .5 * (1 + math.erf(x / math.sqrt(2)))
def fm(x): return str(x).replace('.', ',')

def analyze(r, hist, div):
    Fh, Fa = form(hist, r['HomeTeam']), form(hist, r['AwayTeam'])
    if not Fh or not Fa: return []
    lg = lgavg(hist); out = []
    t = r.get('Time') or ''
    if t:
        h, m = t.split(':'); t = '%02d:%s' % ((int(h) + 1) % 24, m)  # hora UK -> España
    def add(mk, sel, p, real, note, lo=.1):
        if lo <= p <= .96:
            out.append(dict(h=r['HomeTeam'], a=r['AwayTeam'], lg=LG[div], t=t, mk=mk, s=sel, p=round(p, 4), r=real, n=note))
    def mu(k):
        if not Fh[k] or not Fa[k]: return None
        s = lambda v, c: (c * v + 4 * lg[k]) / (c + 4)
        return ((s(Fh[k][0], Fh[k][2]) + s(Fa[k][1], Fa[k][2])) / 2, (s(Fa[k][0], Fa[k][2]) + s(Fh[k][1], Fh[k][2])) / 2)
    G = mu('g')
    if G:
        h = d = a = o = b = 0
        for i in range(10):
            for j in range(10):
                p = pois(i, G[0]) * pois(j, G[1])
                if i > j: h += p
                elif i == j: d += p
                else: a += p
                if i + j > 2: o += p
                if i and j: b += p
        note = 'Goles esperados %s' % fm(round(G[0] + G[1], 2))
        B = lambda k: n(r.get(k)) if n(r.get(k)) > 1 else None
        o3 = [B('B365H'), B('B365D'), B('B365A')]; o2 = [B('B365>2.5'), B('B365<2.5')]
        def mix(ps, os):
            if not all(os): return ps
            s = sum(1 / x for x in os)
            return [(p + (1 / x) / s) / 2 for p, x in zip(ps, os)]
        p3 = mix([h, d, a], o3); p2 = mix([o, 1 - o], o2)
        for sel, p, od in zip([r['HomeTeam'], 'Empate', r['AwayTeam']], p3, o3): add('Resultado final (1X2)', sel, p, od, note)
        add('Más/Menos 2,5 goles', 'Más de 2,5', p2[0], o2[0], note); add('Más/Menos 2,5 goles', 'Menos de 2,5', p2[1], o2[1], note)
        add('Ambos marcan', 'Sí', b, None, note); add('Ambos marcan', 'No', 1 - b, None, note)
        add('Doble oportunidad', '1X · ' + r['HomeTeam'] + ' o empate', h + d, None, note)
        add('Doble oportunidad', 'X2 · ' + r['AwayTeam'] + ' o empate', a + d, None, note)
    for k in 'cys':
        M = mu(k)
        if not M: continue
        tot = M[0] + M[1]; sd = math.sqrt(tot * PH[k]); base = math.floor(tot) + .5
        note = 'Esperado %s (%s %s · %s %s)' % (fm(round(tot, 2)), r['HomeTeam'], fm(round(M[0], 2)), r['AwayTeam'], fm(round(M[1], 2)))
        for L in (base - 1, base, base + 1):
            p = 1 - Phi((L - tot) / sd)
            add(NM[k], 'Más de ' + fm(L), p, None, note, .2); add(NM[k], 'Menos de ' + fm(L), 1 - p, None, note, .2)
        for team, m in ((r['HomeTeam'], M[0]), (r['AwayTeam'], M[1])):
            sdt = math.sqrt(m * PH[k]); bt = math.floor(m) + .5
            for L in (bt - 1, bt, bt + 1):
                p = 1 - Phi((L - m) / sdt)
                add(NMT[k] + ' · ' + team, 'Más de ' + fm(L), p, None, 'Esperado %s' % fm(round(m, 2)), .2); add(NMT[k] + ' · ' + team, 'Menos de ' + fm(L), 1 - p, None, 'Esperado %s' % fm(round(m, 2)), .2)
        d = M[0] - M[1]; sdd = math.sqrt(tot * PH[k])
        ph = 1 - Phi((.5 - d) / sdd); pa = Phi((-.5 - d) / sdd)
        add(MOST[k], r['HomeTeam'], ph, None, note); add(MOST[k], 'Empate', max(0, 1 - ph - pa), None, note); add(MOST[k], r['AwayTeam'], pa, None, note)
    return out


# ---------- Jugadores (opcional): API-Football, clave en GitHub Secrets (APIFOOTBALL_KEY) ----------
AF = 'https://v3.football.api-sports.io'
AFL = {140: 'LaLiga', 39: 'Premier League', 135: 'Serie A', 78: 'Bundesliga', 61: 'Ligue 1'}
PL = [('Faltas cometidas (jugador)', 'fc', (1, 2)), ('Faltas recibidas (jugador)', 'fd', (1, 2)), ('Remates a puerta (jugador)', 'sot', (1,)),
      ('Remates (jugador)', 'sh', (1, 2)), ('Tarjeta amarilla (jugador)', 'yc', (1,))]

def af(path, key):
    rq = urllib.request.Request(AF + path, headers={'x-apisports-key': key})
    j = json.loads(urllib.request.urlopen(rq, timeout=40).read().decode())
    er = j.get('errors')
    if er and (er if isinstance(er, list) else list(er.values())): raise RuntimeError(str(er))
    return j

def norm(x):
    x = unicodedata.normalize('NFKD', x).encode('ascii', 'ignore').decode().lower()
    return ' '.join(w for w in re.sub(r'[^a-z0-9 ]', ' ', x).split() if w not in ('fc', 'cf', 'ac', 'as', 'sc', 'ssc', 'afc', 'de', 'rc', 'ud', 'cd'))

def same(a, b):
    a, b = norm(a), norm(b)
    return a == b or a in b or b in a or any(len(w) >= 4 and w in b.split() for w in a.split())

def squad(tid, season, key, cache):
    c = cache.get(str(tid))
    if c and time.time() - c['t'] < 7 * 86400: return c['p']
    out = {}
    for pg in (1, 2, 3):
        j = af('/players?team=%s&season=%s&page=%d' % (tid, season, pg), key)
        for x in j.get('response', []):
            o = out.setdefault(x['player']['name'], dict(n=x['player']['name'], ap=0, mi=0, sh=0, sot=0, fc=0, fd=0, yc=0))
            for st in x.get('statistics', []):
                g = lambda v: v or 0
                o['ap'] += g(st['games'].get('appearences')); o['mi'] += g(st['games'].get('minutes'))
                o['sh'] += g(st['shots'].get('total')); o['sot'] += g(st['shots'].get('on'))
                o['fc'] += g(st['fouls'].get('committed')); o['fd'] += g(st['fouls'].get('drawn')); o['yc'] += g(st['cards'].get('yellow'))
        if pg >= (j.get('paging') or {}).get('total', 1): break
    cache[str(tid)] = dict(t=time.time(), p=list(out.values()))
    return cache[str(tid)]['p']

def players(days, fdfix, res, key):
    cache = json.load(open('players_cache.json')) if os.path.exists('players_cache.json') else {}
    try:
        for d in days:
            for f in af('/fixtures?date=%s&timezone=Europe/Madrid' % d.isoformat(), key).get('response', []):
                lg = f['league']['id']
                if lg not in AFL or f['fixture']['status']['short'] != 'NS': continue
                H, A = f['teams']['home'], f['teams']['away']
                h, a = H['name'], A['name']
                for fx in fdfix:
                    if fx['d'] == d and same(fx['h'], h) and same(fx['a'], a): h, a = fx['h'], fx['a']; break
                for tid, tn in ((H['id'], H['name']), (A['id'], A['name'])):
                    sq = sorted([p for p in squad(tid, f['league']['season'], key, cache) if p['ap'] >= 8 and p['mi'] / p['ap'] >= 45], key=lambda p: -p['mi'])[:8]
                    for p in sq:
                        for mk, k, ks in PL:
                            lam = p[k] / p['ap']
                            for n in ks:
                                pr = 1 - math.exp(-lam) * (1 + lam if n == 2 else 1)
                                if .1 <= pr <= .9:
                                    res[d.isoformat()].append(dict(h=h, a=a, lg=AFL[lg], t=f['fixture']['date'][11:16], mk=mk, s='%s (%s) – %d o más' % (p['name'] if 'name' in p else p['n'], tn, n),
                                                                  p=round(pr, 4), r=None, n='Media %s por partido en %d partidos. Supone que juega.' % (fm(round(lam, 2)), p['ap'])))
    except Exception as e:
        print('jugadores:', e)
    json.dump(cache, open('players_cache.json', 'w'))

# ---------- Tenis ATP: modelo propio con historial (Jeff Sackmann, tennis_atp, CC BY-NC-SA) + partidos de The Odds API (ODDS_API_KEY) ----------
SK = 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/'
CLAY = ['roland', 'french', 'madrid', 'rome', 'italian', 'monte', 'barcelona', 'hamburg', 'bastad', 'gstaad', 'umag', 'kitzbuhel', 'bucharest', 'estoril', 'marrakech', 'houston', 'geneva', 'lyon', 'buenos', 'rio ', 'santiago', 'cordoba', 'bogota']
GRASS = ['wimbledon', 'queen', 'halle', 'hertogenbosch', 'eastbourne', 'mallorca', 'newport']
SLAM = ['australian', 'roland', 'french', 'wimbledon', 'us open']

def tn(x):
    x = unicodedata.normalize('NFKD', x).encode('ascii', 'ignore').decode().lower().replace('-', ' ')
    return ' '.join(re.sub(r'[^a-z ]', ' ', x).split())

def elo_data(y):
    ms = []
    for yr in (y - 2, y - 1, y):
        for f in ('atp_matches_%d.csv', 'atp_matches_qual_chall_%d.csv'):
            try:
                rq = urllib.request.Request(SK + f % yr, headers={'User-Agent': 'Mozilla/5.0'})
                ms += rows(urllib.request.urlopen(rq, timeout=60).read().decode('utf-8-sig', 'ignore'))
            except Exception as e: print('historial', yr, f, e)
    ms = [m for m in ms if m.get('winner_name') and m.get('loser_name') and m.get('tourney_date') and 'W/O' not in m.get('score', '')]
    ms.sort(key=lambda m: (m['tourney_date'], int(m.get('match_num') or 0)))
    R, S, hist, h2h, cnt = {}, {}, {}, {}, {}
    for m in ms:
        w, l, sf = tn(m['winner_name']), tn(m['loser_name']), m.get('surface') or ''
        e = 1 / (1 + 10 ** ((R.get(l, 1500) - R.get(w, 1500)) / 400))
        R[w] = R.get(w, 1500) + 32 * (1 - e); R[l] = R.get(l, 1500) - 32 * (1 - e)
        if sf in ('Hard', 'Clay', 'Grass'):
            e = 1 / (1 + 10 ** ((S.get((l, sf), 1500) - S.get((w, sf), 1500)) / 400))
            S[(w, sf)] = S.get((w, sf), 1500) + 32 * (1 - e); S[(l, sf)] = S.get((l, sf), 1500) - 32 * (1 - e)
            for p in (w, l): cnt[(p, sf)] = cnt.get((p, sf), 0) + 1
        hist.setdefault(w, []).append(1); hist.setdefault(l, []).append(0)
        pr = tuple(sorted((w, l))); h2h.setdefault(pr, [0, 0])[0 if w == pr[0] else 1] += 1
    return R, S, hist, h2h, cnt

def find(name, st):
    R = st[0]; k = tn(name)
    if k in R: return k
    t = k.split()
    c = [x for x in R if x.split()[-1:] == t[-1:] and x[:1] == k[:1]]
    return c[0] if len(c) == 1 else None

def predict(a, b, sf, bo5, st):
    R, S, hist, h2h, cnt = st
    if len(hist.get(a, [])) < 10 or len(hist.get(b, [])) < 10: return None
    def comb(p):
        w = min(cnt.get((p, sf), 0) / 30, 1) * .6
        return (1 - w) * R[p] + w * S.get((p, sf), R[p]), S.get((p, sf))
    (ca, sa), (cb, sb) = comb(a), comb(b)
    pr = tuple(sorted((a, b))); hh = h2h.get(pr, [0, 0]); wa, wb = (hh[0], hh[1]) if a == pr[0] else (hh[1], hh[0])
    d = ca - cb + 40 * (wa - wb) / (wa + wb + 3)
    p = 1 / (1 + 10 ** (-d / (350 if bo5 else 400)))
    fa, fb = sum(hist[a][-10:]), sum(hist[b][-10:])
    note = 'Modelo (Elo): %d vs %d%s. Últimos 10: %d-%d vs %d-%d. Cara a cara: %d-%d.' % (
        R[a], R[b], (' · en %s: %d vs %d' % (sf, sa, sb)) if sa and sb else '', fa, len(hist[a][-10:]) - fa, fb, len(hist[b][-10:]) - fb, wa, wb)
    return p, note

DIAG = {}

def tennis(days, key, res):
    D = DIAG.setdefault('tenis', {'torneos': [], 'historial': 0, 'error': ''})
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo('Europe/Madrid'); now = dt.datetime.now(tz); base = 'https://api.the-odds-api.com/v4'
        st = elo_data(now.year); D['historial'] = sum(len(v) for v in st[2].values())
        if D['historial'] < 2000: st = None
        def q(p):
            rq = urllib.request.Request(base + p + ('&' if '?' in p else '?') + 'apiKey=' + key, headers={'User-Agent': 'Mozilla/5.0'})
            return json.loads(urllib.request.urlopen(rq, timeout=40).read().decode())
        for sp in q('/sports'):
            if not sp['key'].startswith('tennis_atp'): continue
            ti = (sp['title'] + ' ' + sp['key'].replace('_', ' ')).lower(); mm = int(any(c in ti for c in MASTERS))
            info = {'t': sp['title'], 'activo': bool(sp.get('active')), 'eventos': 0, 'en_3_dias': 0, 'sin_datos': 0, 'añadidos': 0}
            if sp.get('active') and not mm: D['torneos'].append(info)
            if not sp.get('active') or mm: continue
            sf = 'Clay' if any(c in ti for c in CLAY) else 'Grass' if any(c in ti for c in GRASS) else 'Hard'; bo5 = any(c in ti for c in SLAM)
            try: evs = q('/sports/%s/odds?regions=eu&markets=h2h&oddsFormat=decimal' % sp['key'])
            except Exception as e: print('tenis', sp['key'], e); info['error'] = str(e)[:80]; continue
            for e in evs:
                info['eventos'] += 1
                t = dt.datetime.fromisoformat(e['commence_time'].replace('Z', '+00:00')).astimezone(tz)
                if t.date() not in days or t <= now: continue
                info['en_3_dias'] += 1
                A, B = e['home_team'], e['away_team']; pr = None
                if st:
                    ka, kb = find(A, st), find(B, st)
                    if ka and kb: pr = predict(ka, kb, sf, bo5, st)
                ps = {A: [], B: []}; b365 = {}
                for bk in e.get('bookmakers', []):
                    for m in bk.get('markets', []):
                        if m['key'] != 'h2h': continue
                        o = {x['name']: x['price'] for x in m['outcomes']}
                        if A in o and B in o and o[A] > 1 and o[B] > 1:
                            z = 1 / o[A] + 1 / o[B]; ps[A].append(1 / o[A] / z); ps[B].append(1 / o[B] / z)
                            if bk['key'] == 'bet365': b365 = o
                nb = len(ps[A])
                if not pr and nb < 2: info['sin_datos'] += 1; continue
                for me, pm in ((A, pr[0] if pr else None), (B, 1 - pr[0] if pr else None)):
                    mkt = sum(ps[me]) / nb if nb else None
                    p = pm if mkt is None else mkt if pm is None else (.7 * pm + .3 * mkt if nb >= 3 else pm)
                    nt = (pr[1] if pr else 'Sin historial suficiente de algún jugador.') + (' Mezcla 70%% modelo + 30%% mercado (%d casas).' % nb if pr and nb >= 3 else ' Solo modelo.' if pr else ' Solo mercado (%d casas).' % nb) + ' Superficie supuesta: %s.' % sf
                    if .08 <= p <= .96:
                        res[t.date().isoformat()].append(dict(sp='tenis', mm=mm, h=A, a=B, lg=sp['title'] + (' · Masters 1000' if mm else ''), t=t.strftime('%H:%M'), mk='Ganador del partido', s=me, p=round(p, 4), r=b365.get(me), n=nt))
                        info['añadidos'] += 1
    except Exception as e:
        print('tenis:', e); m = str(e); D['error'] = ('Clave de The Odds API no válida (401).' if '401' in m else 'Sin créditos o límite de The Odds API (429).' if '429' in m else m[:120])

# ---------- Simulación y aprendizaje ----------
MASTERS = ['indian wells', 'miami', 'monte', 'madrid', 'rome', 'italian', 'canad', 'toronto', 'montreal', 'cincinnati', 'shanghai', 'paris']
STAT = {'Córners': ('HC', 'AC'), 'Remates a puerta': ('HST', 'AST'), 'Remates': ('HS', 'AS')}
MOSTK = {'Más córners': 'Córners', 'Más tarjetas': 'Tarjetas', 'Más remates a puerta': 'Remates a puerta', 'Más remates': 'Remates'}

def sstat(row, k):
    if k == 'Tarjetas': return n(row.get('HY')) + n(row.get('HR') or 0), n(row.get('AY')) + n(row.get('AR') or 0)
    a, b = STAT[k]; return n(row.get(a)), n(row.get(b))

def lnum(s): return float(re.search(r'\d+(?:[,.]\d+)?', s).group().replace(',', '.'))

def outcome_f(e, row):
    mk, s = e['mk'], e['s']; H, A = row['HomeTeam'], row['AwayTeam']; hg, ag = n(row.get('FTHG')), n(row.get('FTAG'))
    if math.isnan(hg + ag): return None
    if mk.startswith('Resultado final'): return s == (H if hg > ag else A if ag > hg else 'Empate')
    if mk.startswith('Más/Menos 2,5'): return (hg + ag > 2.5) == s.startswith('Más')
    if mk.startswith('Ambos'): return (hg > 0 and ag > 0) == (s == 'Sí')
    if mk.startswith('Doble'): return (hg >= ag) if s.startswith('1X') else (ag >= hg)
    base = mk.split(' · ')[0]
    try:
        if base in MOSTK:
            a, b = sstat(row, MOSTK[base])
            if math.isnan(a + b): return None
            return s == (H if a > b else A if b > a else 'Empate')
        for k in ('Remates a puerta', 'Córners', 'Tarjetas', 'Remates'):
            if base == k + ' totales' or base == k + ' de equipo':
                a, b = sstat(row, k)
                if math.isnan(a + b): return None
                v = a + b if base.endswith('totales') else (a if mk.split(' · ')[1] == H else b)
                return (v > lnum(s)) == s.startswith('Más')
    except Exception: return None
    return None

def tennis_scores(key):
    out = []
    try:
        base = 'https://api.the-odds-api.com/v4'
        def q(p):
            rq = urllib.request.Request(base + p + ('&' if '?' in p else '?') + 'apiKey=' + key, headers={'User-Agent': 'Mozilla/5.0'})
            return json.loads(urllib.request.urlopen(rq, timeout=40).read().decode())
        for sp in q('/sports'):
            if not (sp.get('active') and sp['key'].startswith('tennis_atp')): continue
            try:
                for g in q('/sports/%s/scores?daysFrom=3' % sp['key']):
                    if not (g.get('completed') and g.get('scores')): continue
                    sc = {tn(x['name']): n(x['score']) for x in g['scores']}; nm = {tn(x['name']): x['name'] for x in g['scores']}
                    if len(sc) == 2 and not any(math.isnan(v) for v in sc.values()) and len(set(sc.values())) == 2:
                        out.append(dict(d=(g.get('commence_time') or '')[:10], h=g['home_team'], a=g['away_team'], w=nm[max(sc, key=sc.get)]))
            except Exception as e: print('scores', sp['key'], e)
    except Exception as e: print('scores:', e)
    return out

def fam(e):
    sx = e['s']; d = 'M' if 'Más de' in sx else 'm' if 'Menos de' in sx else ''
    return '%s|%s|%s' % (e.get('sp', 'futbol'), e['mk'].split(' · ')[0], d)

def eff(e): return e.get('r') or max(1.01, 1 / (e['p'] * 1.06))

def combo(L, need):
    by = {}
    for x in L:
        if eff(x) >= 1.1: by.setdefault(x['h'] + x['a'], []).append(x)
    M = [sorted(v, key=lambda x: -x['p'])[:8] for v in by.values()]; hi = need * 1.25
    S = {(0, 0): (1.0, 0.0, [])}
    for c in M:
        N = dict(S)
        for o, l, a in list(S.values()):
            if len(a) >= 10: continue
            for x in c:
                o2 = o * eff(x)
                if o2 > hi: continue
                l2 = l + math.log(x['p']) - .03; k = (len(a) + 1, round(math.log(o2) * 50))
                if k not in N or l2 > N[k][1]: N[k] = (o2, l2, a + [x])
        S = N
    B = None
    for o, l, a in S.values():
        if a and need <= o <= hi and (B is None or l > B[1]): B = (o, l, a)
    return B

def simulate(res, days, RES, tkey):
    import hashlib
    from zoneinfo import ZoneInfo
    try: sim = json.load(open('data.json', encoding='utf-8')).get('sim') or {}
    except Exception: sim = {}
    for k, v in (('bets', []), ('cal', []), ('seen', []), ('stats', {}), ('bk', {})): sim.setdefault(k, v)
    today = days[0]; age = lambda d: (today - dt.date.fromisoformat(d)).days
    pend_t = any(x.get('sp') == 'tenis' for x in sim['cal']) or any(l.get('sp') == 'tenis' and l.get('ok') is None for b in sim['bets'] if b['status'] == 'pend' for l in b['legs'])
    tr = sim.setdefault('tr', []); known = {(x['d'], x['h'], x['a']) for x in tr}
    if tkey and (dt.datetime.utcnow().hour >= 12 or not tr):
        for x in tennis_scores(tkey):
            if (x['d'], x['h'], x['a']) not in known: tr.append(x)
    sim['tr'] = [x for x in tr if x['d'] and age(x['d']) <= 30]
    TS = {frozenset((tn(x['h']), tn(x['a']))): tn(x['w']) for x in sim['tr']}
    def out(e, d):
        if e.get('sp') == 'tenis':
            w = TS.get(frozenset((tn(e['h']), tn(e['a'])))); return None if w is None else tn(e['s']) == w
        row = RES.get((e['h'], e['a'], d)); return None if row is None else outcome_f(e, row)
    keep = []
    for c in sim['cal']:
        o = out(c, c['d'])
        if o is None:
            if age(c['d']) <= 14: keep.append(c)
            continue
        sp = c.get('sp', 'futbol'); st = sim['stats'].setdefault(fam(c), [0, 0, 0.0]); st[0] += 1; st[1] += int(o); st[2] += c['p0']
        bb = sim['bk'].setdefault(sp, {}).setdefault(str(min(9, int(c['p0'] * 10))), [0, 0, 0.0]); bb[0] += 1; bb[1] += int(o); bb[2] += c['p0']
    sim['cal'] = keep
    for b in sim['bets']:
        if b['status'] != 'pend': continue
        for l in b['legs']:
            if l.get('ok') is None: l['ok'] = out(l, b['date'])
        if any(l['ok'] is False for l in b['legs']): b['status'] = 'loss'
        elif all(l['ok'] is True for l in b['legs']): b['status'] = 'win'
        elif age(b['date']) > 14: b['status'] = 'void'
    F = {k: round(max(.8, min(1.2, (h + 10) / (ps + 10))), 3) for k, (n_, h, ps) in sim['stats'].items() if n_ >= 30}
    sim['factors'] = F
    nowm = dt.datetime.now(ZoneInfo('Europe/Madrid')).strftime('%H:%M')
    for d, L in res.items():
        for e in L:
            e['p0'] = e['p']; f = F.get(fam(e))
            if f: e['p'] = round(min(.97, max(.02, e['p'] * f)), 4)
    seen = set(sim['seen'])
    for d, L in res.items():
        for e in L:
            if d == today.isoformat() and e.get('t') and e['t'] <= nowm: continue
            idk = '|'.join((d, e['h'], e['a'], e['mk'], e['s']))
            if idk in seen or int(hashlib.md5(idk.encode()).hexdigest()[:6], 16) % 30: continue
            seen.add(idk); sim['seen'].append(idk)
            sim['cal'].append(dict(d=d, sp=e.get('sp', 'futbol'), h=e['h'], a=e['a'], mk=e['mk'], s=e['s'], p0=e['p0']))
    sim['seen'] = sim['seen'][-6000:]
    L0 = [e for e in res.get(today.isoformat(), []) if not e.get('t') or e['t'] > nowm]
    for sp in ('futbol',):
        for tg in (2, 5):
            bid = '%s|%s|%d' % (today.isoformat(), sp, tg)
            if any(b['id'] == bid for b in sim['bets']): continue
            B = combo([e for e in L0 if e.get('sp', 'futbol') == sp], tg)
            if B: sim['bets'].append(dict(id=bid, date=today.isoformat(), sp=sp, target=tg, stake=10, odds=round(B[0], 2), p=round(math.prod(x['p'] for x in B[2]), 4), status='pend',
                legs=[dict(sp=sp, h=x['h'], a=x['a'], mk=x['mk'], s=x['s'], eff=round(eff(x), 2), p=x['p'], ok=None) for x in B[2]]))
    sim['bets'] = sim['bets'][-300:]
    return sim

# ---------- Calendario de respaldo: openfootball (dominio público, sin clave) ----------
# football-data.co.uk publica el fin de semana el viernes por la tarde (y los entre semana el martes), así que
# los partidos de jueves-viernes a veces faltan. openfootball tiene el calendario completo de la temporada.
OF = {'SP1': 'es.1', 'SP2': 'es.2', 'E0': 'en.1', 'E1': 'en.2', 'E2': 'en.3', 'I1': 'it.1', 'I2': 'it.2', 'D1': 'de.1', 'D2': 'de.2',
      'F1': 'fr.1', 'F2': 'fr.2', 'N1': 'nl.1', 'P1': 'pt.1', 'B1': 'be.1', 'T1': 'tr.1', 'SC0': 'sco.1', 'G1': 'gr.1'}
CET = ('es', 'de', 'it', 'fr', 'nl', 'be')
STOP = {'fc', 'cf', 'afc', 'sc', 'ac', 'as', 'rc', 'rcd', 'ud', 'cd', 'sd', 'sv', 'vfb', 'vfl', 'tsg', 'fsv', 'club', 'de', 'calcio', 'sk', 'bsc', 'ssc', 'us', 'og', 'the'}
_AL = {'atletico madrid': 'ath madrid', 'club atletico de madrid': 'ath madrid', 'athletic club': 'ath bilbao', 'athletic bilbao': 'ath bilbao', 'real betis': 'betis', 'real sociedad': 'sociedad',
       'rayo vallecano': 'vallecano', 'celta vigo': 'celta', 'espanyol': 'espanol', 'deportivo alaves': 'alaves', 'inter milan': 'inter', 'internazionale milano': 'inter', 'ac milan': 'milan',
       'wolverhampton wanderers': 'wolves', 'nottingham forest': "nott'm forest", 'borussia monchengladbach': "m'gladbach", 'borussia dortmund': 'dortmund', 'bayer leverkusen': 'leverkusen',
       'eintracht frankfurt': 'ein frankfurt', 'paris saint germain': 'paris sg', 'olympique marseille': 'marseille', 'olympique lyonnais': 'lyon', 'tottenham hotspur': 'tottenham',
       'brighton hove albion': 'brighton', 'west ham united': 'west ham', 'newcastle united': 'newcastle', 'leicester city': 'leicester', 'manchester united': 'man united', 'manchester city': 'man city',
       'bayern munchen': 'bayern munich', 'hellas verona': 'verona', 'sporting clube de portugal': 'sporting cp', 'sporting cp': 'sporting cp', 'sl benfica': 'benfica', 'psv eindhoven': 'psv'}
def nrm(x): return tn(x)
ALIAS2 = {nrm(k): v for k, v in _AL.items()}
def tkey_(x): return ' '.join(t for t in nrm(x).split() if t not in STOP)
ALIAS3 = {tkey_(k): v for k, v in _AL.items()}

def mapteam(name, cands):
    CK = {tkey_(c): c for c in cands}; k = tkey_(name)
    if k in CK: return CK[k]
    a = ALIAS2.get(nrm(name)) or ALIAS2.get(k)
    if a and tkey_(a) in CK: return CK[tkey_(a)]
    tk = k.split(); best = []
    for ak in sorted(ALIAS3, key=lambda z: -len(z.split())):
        if set(ak.split()) <= set(tk) and tkey_(ALIAS3[ak]) in CK: return CK[tkey_(ALIAS3[ak])]
    for ck, c in CK.items():
        ct = ck.split()
        if ct and all(any(w.startswith(t) for w in tk) for t in ct): best.append((len(ct), c))
        elif tk and all(any(t.startswith(w) for w in ct) for t in tk): best.append((len(tk), c))
    if best:
        best.sort(reverse=True)
        if len(best) == 1 or best[0][0] > best[1][0]: return best[0][1]
    m = difflib.get_close_matches(k, list(CK), n=1, cutoff=.75)
    return CK[m[0]] if m else None

def of_fixtures(div, y, days, cands, miss):
    out = []; code = OF.get(div)
    if not code: return out
    try:
        rq = urllib.request.Request('https://raw.githubusercontent.com/openfootball/football.json/master/%d-%02d/%s.json' % (y, (y + 1) % 100, code), headers={'User-Agent': 'Mozilla/5.0'})
        j = json.loads(urllib.request.urlopen(rq, timeout=40).read().decode())
    except Exception as e:
        print('openfootball', div, e); return out
    ms = j.get('matches') or [m for r in j.get('rounds', []) for m in r.get('matches', [])]
    for m in ms:
        try: d = dt.date.fromisoformat(m['date'][:10])
        except Exception: continue
        if d not in days: continue
        t1, t2 = m['team1'], m['team2']
        t1 = t1['name'] if isinstance(t1, dict) else t1; t2 = t2['name'] if isinstance(t2, dict) else t2
        h, a = mapteam(t1, cands), mapteam(t2, cands)
        if not h or not a: miss.append('%s-%s' % (t1, t2)); continue
        tm = (m.get('time') or '')[:5]
        if tm and code[:2] in CET:
            hh, mm = tm.split(':'); tm = '%02d:%s' % ((int(hh) - 1) % 24, mm)
        elif code[:2] in ('tr', 'gr'): tm = ''
        out.append({'Div': div, 'Date': d.strftime('%d/%m/%Y'), 'Time': tm, 'HomeTeam': h, 'AwayTeam': a})
    return out

def main():
    today = dt.date.today(); days = [today + dt.timedelta(i) for i in range(3)]
    y = today.year if today.month >= 7 else today.year - 1
    fx = rows(get('fixtures.csv')); res = {d.isoformat(): [] for d in days}; fdfix = []; RES = {}; DF = {'csv': 0, 'extra': 0}; miss = []
    for div in LG:
        hist = []
        for s in (y - 1, y):
            try: hist += rows(get('mmz4281/%02d%02d/%s.csv' % (s % 100, (s + 1) % 100, div)))
            except Exception as e: print('sin', div, s, e)
        hist = sorted([x for x in hist if x.get('FTHG') and x.get('Date')], key=lambda x: pdate(x['Date']))
        for x in hist: RES[(x['HomeTeam'], x['AwayTeam'], pdate(x['Date']).isoformat())] = x
        mine = [r for r in fx if r.get('Div') == div and r.get('Date')]
        have = {(pdate(r['Date']), r['HomeTeam'], r['AwayTeam']) for r in mine}
        cands = {x['HomeTeam'] for x in hist} | {x['AwayTeam'] for x in hist}
        extra = [r for r in of_fixtures(div, y, days, cands, miss) if (pdate(r['Date']), r['HomeTeam'], r['AwayTeam']) not in have]
        DF['extra'] += len(extra)
        for r in mine + extra:
            d = pdate(r['Date'])
            if d in days:
                if r in mine: DF['csv'] += 1
                res[d.isoformat()] += analyze(r, hist, div); fdfix.append(dict(d=d, h=r['HomeTeam'], a=r['AwayTeam']))
    DIAG['futbol'] = {'football_data': DF['csv'], 'openfootball': DF['extra'], 'sin_mapear': miss[:8]}
    key = os.environ.get('APIFOOTBALL_KEY', '').strip()
    if key: players(days, fdfix, res, key)
    tkey = ''  # tenis desactivado (sin clave de The Odds API)
    try: sim = simulate(res, days, RES, tkey)
    except Exception as e: print('simulación:', e); sim = {}
    cl = lambda v: None if (v is None or math.isnan(v)) else v
    cut = (today - dt.timedelta(days=12)).isoformat(); rf = []
    for (h, a, d), x in RES.items():
        if d >= cut:
            v = V(x); rf.append({'d': d, 'h': h, 'a': a, 'g': [cl(t) for t in v['g']], 'c': [cl(t) for t in v['c']], 'y': [cl(t) for t in v['y']], 's': [cl(t) for t in v['s']], 't': [cl(t) for t in v['t']]})
    json.dump({'updated': dt.datetime.utcnow().isoformat() + 'Z', 'days': res, 'sim': sim, 'diag': DIAG, 'results': {'f': rf}}, open('data.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print({k: len(v) for k, v in res.items()})

if __name__ == '__main__': main()
