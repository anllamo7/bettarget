"""Descarga datos gratuitos de football-data.co.uk (sin clave), calcula probabilidades
con los últimos partidos de cada equipo y escribe data.json para los próximos 3 días."""
import csv, io, json, math, urllib.request, datetime as dt
BASE = 'https://www.football-data.co.uk/'
LG = {'SP1': 'LaLiga', 'E0': 'Premier League', 'I1': 'Serie A', 'D1': 'Bundesliga', 'F1': 'Ligue 1'}
PH = {'c': 1.4, 'y': 1.25, 'f': 1.5}
NM = {'c': 'Córners totales', 'y': 'Tarjetas totales (amarillas+rojas)', 'f': 'Faltas totales'}

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
            'f': (n(x.get('HF')), n(x.get('AF')))}

def form(hist, t):
    m = [x for x in hist if t in (x['HomeTeam'], x['AwayTeam'])][-8:]
    if len(m) < 5: return None
    o = {}
    for k in 'gcyf':
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
    for k in 'gcyf':
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
    def add(mk, sel, p, real, note):
        if .3 <= p <= .96:
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
    for k in 'cyf':
        M = mu(k)
        if not M: continue
        tot = M[0] + M[1]; sd = math.sqrt(tot * PH[k]); base = math.floor(tot) + .5
        note = 'Esperado %s (%s %s · %s %s)' % (fm(round(tot, 2)), r['HomeTeam'], fm(round(M[0], 2)), r['AwayTeam'], fm(round(M[1], 2)))
        for L in (base - 1, base, base + 1):
            p = 1 - Phi((L - tot) / sd)
            add(NM[k], 'Más de ' + fm(L), p, None, note); add(NM[k], 'Menos de ' + fm(L), 1 - p, None, note)
    return out

def main():
    today = dt.date.today(); days = [today + dt.timedelta(i) for i in range(3)]
    y = today.year if today.month >= 7 else today.year - 1
    fx = rows(get('fixtures.csv')); res = {d.isoformat(): [] for d in days}
    for div in LG:
        hist = []
        for s in (y - 1, y):
            try: hist += rows(get('mmz4281/%02d%02d/%s.csv' % (s % 100, (s + 1) % 100, div)))
            except Exception as e: print('sin', div, s, e)
        hist = sorted([x for x in hist if x.get('FTHG') and x.get('Date')], key=lambda x: pdate(x['Date']))
        for r in fx:
            if r.get('Div') != div or not r.get('Date'): continue
            d = pdate(r['Date'])
            if d in days: res[d.isoformat()] += analyze(r, hist, div)
    json.dump({'updated': dt.datetime.utcnow().isoformat() + 'Z', 'days': res}, open('data.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print({k: len(v) for k, v in res.items()})

if __name__ == '__main__': main()
