#!/usr/bin/env python3
"""Reittisuunnittelu: Nominatim -> BRouter (oma profiili) -> GPX + raportti."""
import argparse, json, math, os, re, ssl, sys, time, urllib.error, urllib.parse, urllib.request

UA = "reittisuunnittelu-skill/1.0"
BROUTER = "https://brouter.de/brouter"
KESKUS = (62.7903, 22.8403)   # Seinäjoen keskusta; nimihaun osumista valitaan lähin

COMMON_GLOBAL = """---context:global
assign processUnusedTags = true
assign turnInstructionMode = 0
assign downhillcost = 0
assign uphillcost = 0
assign lit_weight = {LIT}
assign quiet_weight = {QUIET}
"""
NODE = """
---context:node
assign initialcost = 0
"""
SURF = """
assign ispaved = surface=asphalt|paved|concrete
assign isrough = surface=paving_stones|sett
assign isgravel = surface=gravel|fine_gravel|compacted|unpaved
assign isdirt = surface=dirt|earth|ground
assign issoft = surface=grass|sand|mud
assign isknownsurface = or ispaved or isrough or isgravel or isdirt issoft
assign litfactor = if lit=yes then 1
                   else if lit=no then add 1 multiply 3 lit_weight
                   else add 1 multiply 0.7 lit_weight
assign noisefactor = if estimated_noise_class=6 then 2.2 else if estimated_noise_class=5 then 1.8
                     else if estimated_noise_class=4 then 1.4 else if estimated_noise_class=3 then 1.15 else 1.0
assign forestfactor = if estimated_forest_class=4|5|6 then 0.85 else if estimated_forest_class=2|3 then 0.93 else 1.0
assign quietfactor = add 1 multiply quiet_weight sub multiply noisefactor forestfactor 1
assign turncost = 0
assign initialcost = 0
"""

PROFILES = {
"juoksu-katu": ("foot", 2, """
assign validForFoot = true
---context:way
""" + SURF + """
assign isblocked = if foot=yes|designated|permissive then false
                   else or highway=motorway|motorway_link|trunk|trunk_link
                        or access=no|private foot=no
assign basecost = if highway=footway|cycleway|pedestrian then 1.0
                  else if highway=living_street|residential then 1.3
                  else if highway=path|service then 1.4
                  else if highway=track|unclassified then 1.8
                  else if highway=tertiary|tertiary_link then 2.0
                  else if highway=secondary|secondary_link|primary|primary_link then 3.5
                  else if highway=steps then 3.0
                  else 2.5
assign surfacefactor = if ispaved then 1.0 else if isgravel then 1.3 else if or isdirt issoft then 1.8 else 1.1
assign costfactor = if isblocked then 10000 else multiply basecost multiply surfacefactor multiply litfactor quietfactor
"""),
"juoksu-maasto": ("foot", 0, """
assign validForFoot = true
---context:way
""" + SURF + """
assign isblocked = if foot=yes|designated|permissive then false
                   else or highway=motorway|motorway_link|trunk|trunk_link
                        or access=no|private foot=no
assign basecost = if highway=path|track|bridleway then 1.0
                  else if highway=footway then 1.2
                  else if highway=cycleway|pedestrian then 1.5
                  else if highway=unclassified|service then 1.6
                  else if highway=living_street|residential then 1.8
                  else if highway=tertiary|tertiary_link then 2.5
                  else if highway=secondary|secondary_link|primary|primary_link then 4.0
                  else if highway=steps then 2.0
                  else 2.5
assign surfacefactor = if or isgravel isdirt then 1.0 else if issoft then 1.4 else if ispaved then 1.3 else 1.1
assign costfactor = if isblocked then 10000 else multiply basecost multiply surfacefactor multiply litfactor quietfactor
"""),
"gravel": ("bike", 0, """
assign validForBikes = true
---context:way
""" + SURF + """
assign bikeok = bicycle=yes|designated|permissive
assign isblocked = if bikeok then false
                   else or highway=motorway|motorway_link|trunk|trunk_link|steps
                        or access=no|private bicycle=no
assign basecost = if highway=track then if tracktype=grade4|grade5 then 1.6 else 1.0
                  else if highway=unclassified then 1.2
                  else if highway=service|residential|living_street then 1.6
                  else if highway=cycleway then 1.5
                  else if highway=path then if mtb:scale=2|3|4|5|6 then 5 else 1.5
                  else if highway=footway|pedestrian then if bikeok then 1.6 else 3.0
                  else if highway=tertiary|tertiary_link then 2.0
                  else if highway=secondary|secondary_link then 3.5
                  else if highway=primary|primary_link then 5.0
                  else 2.5
assign surfacefactor = if isgravel then 1.0 else if isdirt then 1.3 else if issoft then 2.5
                       else if ispaved then 1.6 else if isrough then 2.0
                       else if highway=track then 1.1 else 1.4
assign costfactor = if isblocked then 10000 else multiply basecost multiply surfacefactor multiply litfactor quietfactor
"""),
"xc-mtb": ("bike", 0, """
assign validForBikes = true
---context:way
""" + SURF + """
assign bikeok = bicycle=yes|designated|permissive
assign isblocked = if bikeok then false
                   else or highway=motorway|motorway_link|trunk|trunk_link
                        or access=no|private bicycle=no
assign basecost = if highway=path|bridleway then if mtb:scale=4|5|6 then 3.0 else 1.0
                  else if highway=track then if tracktype=grade1|grade2 then 1.4 else 1.1
                  else if highway=unclassified then if ispaved then 2.2 else 1.6
                  else if highway=cycleway then 1.8
                  else if highway=footway|pedestrian then if bikeok then 1.8 else 2.5
                  else if highway=service|residential|living_street then 2.0
                  else if highway=tertiary|tertiary_link then 3.0
                  else if highway=secondary|secondary_link then 5.0
                  else if highway=primary|primary_link then 8.0
                  else if highway=steps then 6.0
                  else 2.5
assign surfacefactor = if or isdirt isgravel then 1.0 else if issoft then 1.5 else if ispaved then 1.3 else 1.1
assign costfactor = if isblocked then 10000 else multiply basecost multiply surfacefactor multiply litfactor quietfactor
"""),
"rullaluistelu": ("foot", 1, """
assign validForFoot = true
---context:way
""" + SURF + """
assign smoothbad = smoothness=bad|very_bad|horrible|very_horrible|impassable
assign isblocked = or highway=motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|steps|track|bridleway
                   or access=no|private
                   or isgravel or isdirt or issoft or smoothbad surface=sett
assign pavedenough = if ispaved then true
                     else if isknownsurface then false
                     else highway=cycleway|footway|pedestrian|residential|living_street|service|unclassified|tertiary|tertiary_link
assign basecost = if highway=cycleway then 1.0
                  else if highway=footway|pedestrian then 1.2
                  else if highway=residential|living_street then 1.6
                  else if highway=service then 1.8
                  else if highway=unclassified then 2.0
                  else if highway=tertiary|tertiary_link then 3.0
                  else 2.5
assign surfacefactor = if ispaved then 1.0 else if surface=paving_stones then 3.0 else 1.5
assign costfactor = if or isblocked not pavedenough then 10000
                    else multiply basecost multiply surfacefactor multiply litfactor quietfactor
"""),
}
LIT_LEVELS = {"ei": 0, "suosi": 1, "vahva": 2}
GPX_TYPE = {"juoksu-katu": "running", "juoksu-maasto": "trail_running", "gravel": "cycling",
            "xc-mtb": "mountain_biking", "rullaluistelu": "inline_skating"}
CONNECT_LAJI = {"juoksu-katu": "Juoksu", "juoksu-maasto": "Polkujuoksu", "gravel": "Gravel-pyöräily",
                "xc-mtb": "Maastopyöräily", "rullaluistelu": "Muu (tai Juoksu)"}

def ctx():
    ca = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    return ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()

def http(url, data=None, ctype=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    if ctype: req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx()) as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        host = urllib.parse.urlparse(url).netloc
        sys.exit(f"VIRHE: {host} vastasi {e.code} {e.reason}" +
                 (" (todennäköisesti käyttöraja, yritä hetken päästä)" if e.code in (403, 429) else ""))

def geocode(q):
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*", q)
    if m: return float(m.group(1)), float(m.group(2)), q
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "jsonv2", "limit": 8, "countrycodes": "fi"})
    res = json.loads(http(url)); time.sleep(1.1)
    if not res: sys.exit(f"VIRHE: paikkaa ei löytynyt: {q}")
    c = KESKUS   # valitaan osumista lähin kotiseudun keskustaa
    best = min(res, key=lambda x: (float(x["lat"]) - c[0])**2 + ((float(x["lon"]) - c[1]) * 0.46)**2)
    return float(best["lat"]), float(best["lon"]), best.get("display_name", q)

def dest(lat, lon, bearing, km):
    R = 6371.0; b = math.radians(bearing); p1 = math.radians(lat); l1 = math.radians(lon); d = km / R
    p2 = math.asin(math.sin(p1)*math.cos(d) + math.cos(p1)*math.sin(d)*math.cos(b))
    l2 = l1 + math.atan2(math.sin(b)*math.sin(d)*math.cos(p1), math.cos(d) - math.sin(p1)*math.sin(p2))
    return math.degrees(p2), math.degrees(l2)

def upload_profile(sport, lit, quiet=False):
    """quiet=True: vältetään meluisia (isojen teiden varren) väyliä ja suositaan metsäisiä
    (BRouterin estimated_noise_class / estimated_forest_class)."""
    _, _, body = PROFILES[sport]
    text = COMMON_GLOBAL.replace("{LIT}", str(lit)).replace("{QUIET}", "1" if quiet else "0") + body + NODE
    res = json.loads(http(BROUTER + "/profile", data=text.encode(), ctype="text/plain"))
    if "error" in res and res["error"]: sys.exit("VIRHE profiilissa: " + str(res["error"]))
    return res["profileid"]

def route(points, pid):
    lonlats = "|".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)
    url = BROUTER + "?" + urllib.parse.urlencode({"lonlats": lonlats, "profile": pid,
                                                  "alternativeidx": 0, "format": "geojson"})
    txt = http(url)
    if not txt.lstrip().startswith("{"): sys.exit("VIRHE BRouter: " + txt[:300])
    return json.loads(txt)["features"][0]

def key(lon, lat):
    return (round(float(lon) * 1e6), round(float(lat) * 1e6))

def hav(a, b):
    p1, p2 = math.radians(a[1]), math.radians(b[1]); dl = math.radians(b[0] - a[0])
    h = math.sin((p2 - p1) / 2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2)**2
    return 2 * 6371000.0 * math.asin(math.sqrt(h))

def attach(feat):
    """Liittää kunkin reittipisteen saapuvaan tiehen sen OSM-tagit; palauttaa (pisteet, pituus m)."""
    coords = feat["geometry"]["coordinates"]; msgs = feat["properties"].get("messages") or []
    rows = []
    if len(msgs) > 1:
        h = msgs[0]; iX, iY, iW = h.index("Longitude"), h.index("Latitude"), h.index("WayTags")
        rows = [((int(r[iX]), int(r[iY])), dict(t.split("=", 1) for t in r[iW].split() if "=" in t))
                for r in msgs[1:]]
    pts, m = [], 0
    for i, c in enumerate(coords):
        pts.append((c, rows[m][1] if m < len(rows) else {}))
        if i and m < len(rows) and key(c[0], c[1]) == rows[m][0]: m += 1
    return pts, length(pts)

def spurs(pts):
    """Umpikujapistot: kohdat, joissa reitti kääntyy ja palaa samaa tietä. -> [(kärki, liittymä, pituus m)]"""
    ks = [key(c[0], c[1]) for c, _ in pts]; out = []
    for i in range(1, len(ks) - 1):
        if ks[i-1] != ks[i+1]: continue
        j = 1
        while i - j - 1 >= 0 and i + j + 1 < len(ks) and ks[i-j-1] == ks[i+j+1]: j += 1
        tip, junc = pts[i][0], pts[i-j][0]
        out.append((tip, junc, sum(hav(pts[t-1][0], pts[t][0]) for t in range(i - j + 1, i + 1))))
    return out

def length(pts):
    return sum(hav(pts[i-1][0], pts[i][0]) for i in range(1, len(pts)))

def trim_spurs(pts):
    """Leikkaa edestakaiset pistot pois geometriasta (A-B-kärki-B-A -> A-B-A), kunnes niitä ei ole."""
    while True:
        ks = [key(c[0], c[1]) for c, _ in pts]
        for i in range(1, len(ks) - 1):
            if ks[i-1] != ks[i+1]: continue
            j = 1
            while i - j - 1 >= 0 and i + j + 1 < len(ks) and ks[i-j-1] == ks[i+j+1]: j += 1
            pts = pts[:i-j+1] + pts[i+j+1:]
            break
        else:
            return pts

LOOP_TRIES = 12      # BRouter-kutsuja enintään lenkkiä kohden
LOOP_TURNS = (0, 30, -30, 60, -60, 90, -90, 135, -135, 180)

def loop_route(start, km, suunta, pid):
    """Kolmiolenkki lähtö -> p1 -> p2 -> lähtö. Pistot leikataan pois ja r skaalataan leikatun
    pituuden mukaan. Jos leikattavaa on yli 30 %, suunnassa on umpikujaseutu eikä r:n
    skaalaus auta -> kokeillaan seuraavaa suuntaa. -> (pisteet, pituus m, suunta)"""
    best = None; tries = 0
    for turn in LOOP_TURNS:
        b = suunta + turn; r = km / 4.7
        for _ in range(4):
            if tries >= LOOP_TRIES: return best
            vp = [dest(start[0], start[1], b - 30, r), dest(start[0], start[1], b + 30, r)]
            raw, rawlen = attach(route([start] + vp + [start], pid)); tries += 1
            pts = trim_spurs(raw); ln = length(pts)
            if not best or abs(ln / 1000 - km) < abs(best[1] / 1000 - km): best = (pts, ln, b % 360)
            if abs(ln / 1000 - km) / km < 0.06: return best
            if ln <= 0 or ln < 0.7 * rawlen: break
            r *= km / (ln / 1000)
    return best

def classify(tags):
    lit = {"yes": "valaistu", "no": "valaisematon"}.get(tags.get("lit"), "tuntematon")
    s = tags.get("surface", "")
    surf = ("päällystetty" if s in ("asphalt", "paved", "concrete", "paving_stones", "sett")
            else "päällystämätön" if s else "tuntematon")
    return lit, surf

def analyse(pts):
    stats = {"lit": {}, "surf": {}, "hw": {}, "env": {}}; stretches = []; pos = 0.0; cur = None; asc = 0.0
    base = pts[0][0][2] if len(pts[0][0]) > 2 else None
    for i in range(1, len(pts)):
        c, tags = pts[i]; d = hav(pts[i-1][0], c); lit, surf = classify(tags)
        nc = tags.get("estimated_noise_class", "0"); fc = tags.get("estimated_forest_class", "0")
        ymp = ("meluisa" if nc in ("4", "5", "6") else "metsäinen" if fc in ("2", "3", "4", "5", "6") else "muu")
        for k, v in (("lit", lit), ("surf", surf), ("hw", tags.get("highway", "muu")), ("env", ymp)):
            stats[k][v] = stats[k].get(v, 0) + d
        if lit != "valaistu":
            cur = cur or [pos, pos]; cur[1] = pos + d
        elif cur:
            stretches.append(cur); cur = None
        pos += d
        if base is not None and len(c) > 2:
            if c[2] > base + 3: asc += c[2] - base; base = c[2]
            elif c[2] < base: base = c[2]
    if cur: stretches.append(cur)
    return pos, asc, stats, stretches

def asciify(s):
    s = s.lower().translate(str.maketrans("äöå", "aoa"))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "reitti"

def write_gpx(pts, km, name, sport, outdir):
    fn = os.path.join(outdir, f"{sport}_{asciify(name)}_{km:.1f}km.gpx")
    esc = lambda t: t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    trk = "\n".join(f'      <trkpt lat="{c[1]:.6f}" lon="{c[0]:.6f}">' +
                    (f"<ele>{c[2]:.1f}</ele>" if len(c) > 2 else "") + "</trkpt>" for c, _ in pts)
    gpx = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="reittisuunnittelu" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata><name>{esc(name)}</name></metadata>
  <trk><name>{esc(name)}</name><type>{GPX_TYPE[sport]}</type><trkseg>
{trk}
  </trkseg></trk>
</gpx>
"""
    os.makedirs(outdir, exist_ok=True)
    with open(fn, "w", encoding="utf-8") as f: f.write(gpx)
    return fn

COLORS = {"lit": {"valaistu": "#1D9E75", "valaisematon": "#E24B4A", "tuntematon": "#EF9F27"},
          "surf": {"päällystämätön": "#1D9E75", "päällystetty": "#378ADD", "tuntematon": "#888780"}}

MAPS_MODE = {"juoksu-katu": "walking", "juoksu-maasto": "walking", "rullaluistelu": "walking",
             "gravel": "bicycling", "xc-mtb": "bicycling"}

def maps_url(pts, sport, n=8):
    """Google Maps -reittilinkki: lähtö, maali ja n tasavälein otettua välipistettä reitiltä.
    Maps laskee välit itse, joten reitti voi paikoin poiketa GPX:stä."""
    cum = [0.0]
    for i in range(1, len(pts)): cum.append(cum[-1] + hav(pts[i-1][0], pts[i][0]))
    total = cum[-1]; wps = []; j = 0
    for k in range(1, n + 1):
        t = total * k / (n + 1)
        while j < len(cum) - 1 and cum[j] < t: j += 1
        wps.append(pts[j][0])
    f = lambda c: f"{c[1]:.5f},{c[0]:.5f}"
    return ("https://www.google.com/maps/dir/?api=1&origin=" + f(pts[0][0]) + "&destination=" + f(pts[-1][0])
            + "&waypoints=" + "%7C".join(f(c) for c in wps) + "&travelmode=" + MAPS_MODE.get(sport, "walking"))

def write_preview(pts, km, name, mode, loop, gpxfile, url=None):
    """Esikatselu show_widget-työkalulle: SVG (380 px, värit = valaistus tai pinta).
    Tarkka karttanäkymä tehdään write_map()-funktiolla Artifact-julkaisuun."""
    lat0 = pts[0][0][1]; k = math.cos(math.radians(lat0))
    xs = [c[0] * k for c, _ in pts]; ys = [-c[1] for c, _ in pts]
    w0 = max(xs) - min(xs) or 1e-9; h0 = max(ys) - min(ys) or 1e-9
    s = min(300 / w0, 300 / h0); ox = 40 + (300 - w0 * s) / 2
    P = [(ox + (x - min(xs)) * s, 30 + (y - min(ys)) * s) for x, y in zip(xs, ys)]
    cols = COLORS[mode]; segs = []
    for i in range(1, len(pts)):
        col = cols[classify(pts[i][1])[0 if mode == "lit" else 1]]
        if segs and segs[-1][0] == col:
            lx, ly = segs[-1][1][-1]
            if abs(P[i][0] - lx) + abs(P[i][1] - ly) >= 1.5 or i == len(pts) - 1: segs[-1][1].append(P[i])
        else:
            segs.append((col, [P[i-1], P[i]]))
    paths = "\n".join(f'<path d="M{" L".join(f"{x:.1f} {y:.1f}" for x, y in seg)}" fill="none" stroke="{col}" '
                      'stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>' for col, seg in segs)
    y = 30 + h0 * s + 30
    m_per_px = 1000 / (s / 111.32)
    bar = max(b for b in (50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000) if b / m_per_px <= 130 or b == 50)
    bw = bar / m_per_px; bl = f"{bar // 1000} km" if bar >= 1000 else f"{bar} m"
    used = [c for c in cols if any(cols[c] == col for col, _ in segs)]
    leg = ""
    for j, lab in enumerate(used):
        yy = y + 30 + j * 22
        leg += (f'<line x1="40" y1="{yy}" x2="64" y2="{yy}" stroke="{cols[lab]}" stroke-width="3" stroke-linecap="round"/>'
                f'<text class="ts" x="74" y="{yy}" dominant-baseline="central">{lab}</text>')
    yy = y + 30 + len(used) * 22
    leg += (f'<circle class="c-coral" cx="52" cy="{yy}" r="6" stroke-width="1"/>'
            f'<text class="ts" x="74" y="{yy}" dominant-baseline="central">{"lähtö ja maali" if loop else "lähtö"}</text>')
    marks = f'<circle class="c-coral" cx="{P[0][0]:.1f}" cy="{P[0][1]:.1f}" r="7" stroke-width="1"/>'
    if not loop:
        yy += 22
        marks += f'<circle class="c-gray" cx="{P[-1][0]:.1f}" cy="{P[-1][1]:.1f}" r="7" stroke-width="1"/>'
        leg += (f'<circle class="c-gray" cx="52" cy="{yy}" r="6" stroke-width="1"/>'
                f'<text class="ts" x="74" y="{yy}" dominant-baseline="central">maali</text>')
    H = int(yy + 30)
    esc = lambda t: t.replace("&", "&amp;").replace("<", "&lt;")
    click = f' style="cursor:pointer" onclick="openLink(\'{url}\')"' if url else ""
    btn = ('<button onclick="openLink(\'' + url + '\')" style="display:block;width:100%;margin:0 0 8px;'
           'padding:10px;font-size:15px;border:0.5px solid var(--border-strong);border-radius:var(--radius);'
           'background:var(--surface-1);color:var(--text-primary);cursor:pointer">'
           '<i class="ti ti-map-2" aria-hidden="true"></i> Avaa Google Mapsissa</button>\n') if url else ""
    svg = btn + (f'<svg width="100%" viewBox="0 0 380 {H}" role="img"{click}><title>{esc(name)}</title>'
           f'<desc>Reitin esikatselu, {km:.1f} km, värit: {"valaistus" if mode == "lit" else "pinta"}</desc>\n'
           f'{paths}\n{marks}\n'
           f'<line x1="40" y1="{y:.0f}" x2="{40 + bw:.0f}" y2="{y:.0f}" stroke="#888780" stroke-width="1.5"/>'
           f'<line x1="40" y1="{y - 5:.0f}" x2="40" y2="{y + 5:.0f}" stroke="#888780" stroke-width="1.5"/>'
           f'<line x1="{40 + bw:.0f}" y1="{y - 5:.0f}" x2="{40 + bw:.0f}" y2="{y + 5:.0f}" stroke="#888780" stroke-width="1.5"/>'
           f'<text class="ts" x="{52 + bw:.0f}" y="{y:.0f}" dominant-baseline="central">{bl}</text>\n{leg}\n</svg>\n')
    fn = gpxfile[:-4] + "_esikatselu.html"
    with open(fn, "w", encoding="utf-8") as f: f.write(svg)
    return fn

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
_tiles = {}; _tiles_ok = [True]

def tile_px(lon, lat, z):
    """Web Mercator -pikselikoordinaatit (256 px tiilet) zoomitasolla z."""
    n = 256 * 2 ** z; s = math.sin(math.radians(lat))
    return (lon + 180) / 360 * n, (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n

def fetch_tile(z, x, y):
    """OSM-tiili base64:nä tai None. Ensimmäisen epäonnistumisen jälkeen ei yritetä enää."""
    if (z, x, y) in _tiles: return _tiles[(z, x, y)]
    data = None
    if _tiles_ok[0]:
        try:
            req = urllib.request.Request(TILE_URL.format(z=z, x=x, y=y), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20, context=ctx()) as r:
                import base64; data = base64.b64encode(r.read()).decode("ascii")
        except Exception:
            _tiles_ok[0] = False
    _tiles[(z, x, y)] = data
    return data

def km_points(pts):
    """Kilometrimerkkien sijainnit (lon, lat, km)."""
    out = []; pos = 0.0; nxt = 1000.0
    for i in range(1, len(pts)):
        d = hav(pts[i-1][0], pts[i][0])
        while d and pos + d >= nxt:
            t = (nxt - pos) / d; a, b = pts[i-1][0], pts[i][0]
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, int(nxt / 1000))); nxt += 1000
        pos += d
    return out

def map_svg(pts, mode, loop, z, pad=40):
    """Yksi SVG: OSM-tiilet <image>-elementteinä + reitti valaistuksen/pinnan väreillä + km-merkit."""
    P = [tile_px(c[0], c[1], z) for c, _ in pts]
    x0 = min(p[0] for p in P) - pad; y0 = min(p[1] for p in P) - pad
    W = max(p[0] for p in P) + pad - x0; H = max(p[1] for p in P) + pad - y0
    imgs = []
    for tx in range(int(x0 // 256), int((x0 + W) // 256) + 1):
        for ty in range(int(y0 // 256), int((y0 + H) // 256) + 1):
            d = fetch_tile(z, tx, ty)
            if d: imgs.append(f'<image href="data:image/png;base64,{d}" x="{tx*256 - x0:.0f}" y="{ty*256 - y0:.0f}" '
                              'width="256" height="256"/>')
    Q = [(x - x0, y - y0) for x, y in P]; cols = COLORS[mode]; segs = []
    for i in range(1, len(pts)):
        col = cols[classify(pts[i][1])[0 if mode == "lit" else 1]]
        if segs and segs[-1][0] == col: segs[-1][1].append(Q[i])
        else: segs.append((col, [Q[i-1], Q[i]]))
    line = lambda seg: "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in seg)
    allp = line(Q)
    route = (f'<path d="{allp}" fill="none" stroke="#fff" stroke-width="8" stroke-linejoin="round" '
             'stroke-linecap="round" opacity=".9"/>' +
             "".join(f'<path d="{line(seg)}" fill="none" stroke="{col}" stroke-width="4.5" stroke-linejoin="round" '
                     'stroke-linecap="round"/>' for col, seg in segs))
    marks = ""
    for lon, lat, k in km_points(pts):
        x, y = tile_px(lon, lat, z); x -= x0; y -= y0
        marks += (f'<g class="km"><circle cx="{x:.1f}" cy="{y:.1f}" r="9"/>'
                  f'<text x="{x:.1f}" y="{y:.1f}" dy=".35em" text-anchor="middle">{k}</text></g>')
    sx, sy = Q[0]
    marks += f'<circle class="start" cx="{sx:.1f}" cy="{sy:.1f}" r="8"/>'
    if not loop:
        ex, ey = Q[-1]; marks += f'<circle class="finish" cx="{ex:.1f}" cy="{ey:.1f}" r="8"/>'
    svg = (f'<svg viewBox="0 0 {W:.0f} {H:.0f}" width="{W:.0f}" height="{H:.0f}" role="img" '
           f'aria-label="Reitti kartalla, zoom {z}"><rect width="100%" height="100%" class="bg"/>'
           f'{"".join(imgs)}{route}{marks}</svg>')
    return svg, W, H

def write_map(pts, km, name, mode, loop, gpxfile, info):
    """Itsenäinen HTML-karttasivu Artifact-julkaisuun: koko reitti + tarkka (vieritettävä) näkymä,
    tiilet upotettu data-URI:na (artifaktin CSP estää ulkoiset kuvat)."""
    P = [tile_px(c[0], c[1], 0) for c, _ in pts]
    w0 = max(p[0] for p in P) - min(p[0] for p in P) or 1e-9
    h0 = max(p[1] for p in P) - min(p[1] for p in P) or 1e-9
    z = max(10, min(16, int(math.log2(min(640 / w0, 820 / h0)))))
    over, _, _ = map_svg(pts, mode, loop, z)
    detail, dw, _ = map_svg(pts, mode, loop, min(17, z + 1))
    esc = lambda t: str(t).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
    cols = COLORS[mode]
    used = [c for c in cols if any(classify(t)[0 if mode == "lit" else 1] == c for _, t in pts[1:])]
    leg = "".join(f'<span><i style="background:{cols[c]}"></i>{c}</span>' for c in used)
    leg += '<span><i class="dot start"></i>' + ("lähtö ja maali" if loop else "lähtö") + "</span>"
    if not loop: leg += '<span><i class="dot finish"></i>maali</span>'
    rows = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in info)
    note = ("" if any(_tiles.values()) else
            '<p class="warn">Pohjakartta puuttuu: tile.openstreetmap.org ei ollut tavoitettavissa. '
            'Lisää se Claude-sovelluksen sallittuihin verkkotunnuksiin.</p>')
    html = f"""<title>{esc(name)}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
:root{{--bg:#f4f5f2;--card:#ffffff;--fg:#1f2421;--muted:#5d665f;--line:#d9ddd6;--accent:#1d6f57;--start:#d85a30;--fin:#3c3f45;
--font:"Inter",system-ui,-apple-system,sans-serif;--disp:"Space Grotesk","Inter",system-ui,sans-serif}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#151917;--card:#1e2320;--fg:#e8ece8;--muted:#9aa49d;--line:#2f3632;--accent:#5dcaa5;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#151917;--card:#1e2320;--fg:#e8ece8;--muted:#9aa49d;--line:#2f3632;--accent:#5dcaa5;color-scheme:dark}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 var(--font);padding-block:16px 32px;
padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}}
main{{max-width:760px;margin:0 auto;display:grid;gap:14px}}
h1{{font:500 22px/1.2 var(--disp);margin:0;text-wrap:balance}}
.sub{{color:var(--muted);margin:2px 0 0;font-variant-numeric:tabular-nums}}
.tabs{{display:flex;gap:6px}}
.tabs button{{font:inherit;padding:7px 14px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}}
.tabs button[aria-pressed="true"]{{background:var(--accent);border-color:var(--accent);color:var(--bg)}}
.tabs button:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
.map{{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--card)}}
#v-koko svg{{display:block;width:100%;height:auto}}
#v-tarkka{{overflow:auto;max-height:78vh;-webkit-overflow-scrolling:touch}}
#v-tarkka svg{{display:block;max-width:none}}
.bg{{fill:#e8e6df}}
.km circle{{fill:#fff;stroke:#2b2f2c;stroke-width:1.5}} .km text{{font:600 11px var(--font);fill:#2b2f2c}}
.start{{fill:var(--start);stroke:#fff;stroke-width:3}} .finish{{fill:var(--fin);stroke:#fff;stroke-width:3}}
.legend{{display:flex;flex-wrap:wrap;gap:6px 16px;color:var(--muted);font-size:13px}}
.legend i{{display:inline-block;width:20px;height:5px;border-radius:3px;margin-right:6px;vertical-align:middle}}
.legend i.dot{{width:11px;height:11px;border-radius:50%}} .legend i.start{{background:var(--start)}} .legend i.finish{{background:var(--fin)}}
dl{{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;margin:0;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
dt{{color:var(--muted);font-size:13px;letter-spacing:.02em}} dd{{margin:0;min-width:0;font-variant-numeric:tabular-nums}}
.hint,.attr{{color:var(--muted);font-size:12px;margin:0}} .warn{{color:#b5481f;margin:0}}
</style>
<main>
<header><h1>{esc(name)}</h1><p class="sub">{km:.1f} km · värit: {"valaistus" if mode == "lit" else "pinta"} · numerot = kilometrit</p></header>
{note}
<div class="tabs" role="group" aria-label="Näkymä">
<button id="b-koko" aria-pressed="true">Koko reitti</button><button id="b-tarkka" aria-pressed="false">Tarkka</button></div>
<div class="map" id="v-koko">{over}</div>
<div class="map" id="v-tarkka" hidden>{detail}</div>
<p class="hint" id="hint" hidden>Liikuta karttaa vierittämällä tai pyyhkäisemällä.</p>
<div class="legend">{leg}</div>
<dl>{rows}</dl>
<p class="attr">Pohjakartta © OpenStreetMap-tekijät. Valaistus OSM:n lit-merkinnöistä: tuntematon ei tarkoita pimeää.</p>
</main>
<script>
const v={{koko:document.getElementById('v-koko'),tarkka:document.getElementById('v-tarkka')}};
function show(k){{for(const n in v){{v[n].hidden=n!==k;document.getElementById('b-'+n).setAttribute('aria-pressed',n===k)}}
document.getElementById('hint').hidden=k!=='tarkka';
if(k==='tarkka'&&!v.tarkka.dataset.c){{const s=v.tarkka.querySelector('.start');if(s){{v.tarkka.scrollLeft=s.cx.baseVal.value-v.tarkka.clientWidth/2;v.tarkka.scrollTop=s.cy.baseVal.value-v.tarkka.clientHeight/2}}v.tarkka.dataset.c=1}}}}
document.getElementById('b-koko').onclick=()=>show('koko');document.getElementById('b-tarkka').onclick=()=>show('tarkka');
</script>
"""
    fn = gpxfile[:-4] + "_kartta.html"
    with open(fn, "w", encoding="utf-8") as f: f.write(html)
    return fn

def pct(dct, total):
    return ", ".join(f"{k} {v/total*100:.0f} %" for k, v in sorted(dct.items(), key=lambda x: -x[1]))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--laji", required=True, choices=PROFILES)
    ap.add_argument("--lahto", required=True)
    ap.add_argument("--maali", help="tyhjä = lenkki takaisin lähtöön")
    ap.add_argument("--via", action="append", default=[])
    ap.add_argument("--km", type=float, help="tavoitematka (lenkissä pakollinen)")
    ap.add_argument("--suunta", type=float, default=0, help="lenkin suunta asteina, 0=pohjoinen")
    ap.add_argument("--valaistus", choices=LIT_LEVELS)
    ap.add_argument("--hiljainen", action="store_true",
                    help="suosi hiljaisia pikkuteitä, ulkoilureittejä ja metsää, vältä isojen teiden varsia")
    ap.add_argument("--nimi", default="Reitti")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()

    lit = LIT_LEVELS[a.valaistus] if a.valaistus else PROFILES[a.laji][1]
    pid = upload_profile(a.laji, lit, a.hiljainen)
    start = geocode(a.lahto); vias = [geocode(v) for v in a.via]
    loop = not a.maali
    if loop and not vias and not a.km: sys.exit("VIRHE: lenkkiin tarvitaan --km tai --via")
    end = start if loop else geocode(a.maali)
    base = [(p[0], p[1]) for p in [start] + vias]

    suunta = None
    if loop and not vias:
        pts, _, suunta = loop_route(base[0], a.km, a.suunta, pid)
    else:
        pts, _ = attach(route(base + [(end[0], end[1])], pid))
    spur = sum(ln for _, _, ln in spurs(pts) if ln >= 30)

    total, asc, stats, stretches = analyse(pts)
    fn = write_gpx(pts, total / 1000, a.nimi, a.laji, a.out)
    mode = "lit" if lit > 0 else "surf"
    pv = write_preview(pts, total / 1000, a.nimi, mode, loop, fn)
    long = sorted([s for s in stretches if s[1] - s[0] > 300], key=lambda s: s[0] - s[1])[:3] if total else []
    info = [("Matka", f"{total/1000:.2f} km" + (f" (tavoite {a.km:g} km)" if a.km else "")), ("Nousu", f"{asc:.0f} m")]
    if total:
        info += [("Valaistus", pct(stats["lit"], total)), ("Pinta", pct(stats["surf"], total)),
                 ("Ympäristö", pct(stats["env"], total))]
        if long: info.append(("Ei valomerkintää", ", ".join(f"km {s[0]/1000:.1f}–{s[1]/1000:.1f}" for s in sorted(long))))
    info.append(("Connectissa", CONNECT_LAJI[a.laji]))
    km_file = write_map(pts, total / 1000, a.nimi, mode, loop, fn, info)
    print(f"TIEDOSTO: {fn}")
    print(f"ESIKATSELU: {pv}")
    print(f"KARTTA: {km_file}" + ("" if any(_tiles.values()) else
          " (ilman pohjakarttaa: lisää tile.openstreetmap.org sallittuihin verkkotunnuksiin)"))
    print(f"LAJI: {a.laji} | Connectissa valitse: {CONNECT_LAJI[a.laji]} | valaistuspaino: {lit}")
    print(f"LÄHTÖ: {start[2]}")
    if not loop: print(f"MAALI: {end[2]}")
    print(f"MATKA: {total/1000:.2f} km" + (f" (tavoite {a.km} km)" if a.km else "") + f" | nousu {asc:.0f} m")
    if suunta is not None and abs((suunta - a.suunta + 180) % 360 - 180) > 1:
        print(f"SUUNTA: {suunta:.0f}° (pyydetty {a.suunta % 360:.0f}°, siinä suunnassa umpikujia)")
    if spur > 50: print(f"HUOM: reitissä {spur:.0f} m edestakaisia umpikujapistoja – vaihda --suunta tai lisää --via")
    if total:
        print("VALAISTUS: " + pct(stats["lit"], total))
        print("PINTA: " + pct(stats["surf"], total))
        print("YMPÄRISTÖ: " + pct(stats["env"], total) + " (meluisa = ison tien varsi)")
        print("TIETYYPIT: " + pct(dict(sorted(stats["hw"].items(), key=lambda x: -x[1])[:5]), total))
        for s in sorted(long):
            print(f"VAROITUS: ei valaistusmerkintää km {s[0]/1000:.1f}–{s[1]/1000:.1f} ({(s[1]-s[0]):.0f} m)")

if __name__ == "__main__":
    main()
