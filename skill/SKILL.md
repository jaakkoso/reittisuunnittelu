---
name: reittisuunnittelu
description: Suunnittele juoksu-, pyöräily- tai rullaluistelureitti GPX-tiedostoksi Garmin Connectiin ja Fenixiin. Käytä kun pyydetään lenkkireittiä, reittiä tai GPX:ää.
---

# Reittisuunnittelu (GPX → Garmin Connect → Fenix)

Tekee kartan katuja ja polkuja seuraavan reitin BRouterilla lajikohtaisella profiililla ja palauttaa GPX:n, jonka Jaakko tuo puhelimella Garmin Connectiin ja lähettää Fenixiin.

## Lajit ja profiilit

| laji | painotus | valaistus oletuksena |
|---|---|---|
| `juoksu-katu` | kevyen liikenteen väylät, jalkakäytävät, vältetään isot tiet | suosi vahvasti |
| `juoksu-maasto` | polut ja metsäautotiet | ei väliä |
| `gravel` | sorapintaiset pikkutiet ja metsäautotiet, vältetään päällystetyt päätiet | ei väliä |
| `xc-mtb` | polut ja singletrackit, mtb:scale huomioidaan | ei väliä |
| `rullaluistelu` | vain sileä asfaltti; sora, polut, kiveys ja huono pinta suljetaan pois | suosi |

Enduro-MTB ajetaan `xc-mtb`-profiililla.

## Kysy ensin (vain puuttuvat, yhdellä kertaa)

1. Laji (taulukosta).
2. Lähtö: osoite, paikan nimi tai `lat,lon`.
3. Maali, tai lenkki takaisin lähtöön.
4. Tavoitematka km (lenkissä pakollinen). Jos käyttäjä antaa ajan, muunna: juoksu ~6:00 min/km kevyesti, gravel ~22 km/h, xc-mtb ~16 km/h, rullaluistelu ~18 km/h.
5. Valaistus: `ei`, `suosi`, `vahva`. Pimeän aikaan (loka–maaliskuu klo 16 jälkeen) ehdota juoksuun `vahva`.
6. Lenkissä halutessaan suunta (pohjoinen = 0, itä = 90 …).

Älä kysy kotiosoitetta uudelleen, jos se on muistissa tai keskustelussa.

## Aja

1. Kirjoita alla oleva skripti tiedostoon `reitti.py` työhakemistoon (Write-työkalulla) ja aja Bashilla, esim.:
   ```
   python3 reitti.py --laji juoksu-katu --lahto "62.79,22.84" --km 7 --suunta 270 --valaistus vahva --nimi "Iltalenkki" --out .
   python3 reitti.py --laji gravel --lahto "Seinäjoen asema" --maali "Ilmajoen kirkko" --via "Ahonkylä, Ilmajoki" --nimi "Gravel Ilmajoelle"
   ```
2. Tarkista tulosteen LÄHTÖ- ja MAALI-rivit. Nimihaku (Nominatim) valitsee osumista Seinäjoen keskustaa lähimmän, mutta voi silti osua väärään paikkaan (esim. "rautatieasema" → Ylistaro). Jos paikka on väärä tai haku ei löydä mitään (esim. "Virkistysuimala Pore"), kokeile toista nimeä ("Seinäjoen asema") tai osoitetta, tai hae paikan osoite/koordinaatit verkkohaulla ja anna `lat,lon`.
3. A→B-reitissä: jos matka jää tavoitteesta yli 10 % lyhyeksi, lisää `--via`-piste reitin sivuun ja aja uudelleen (enintään 3 kertaa).
4. Jos raportissa valaisemattomia/tuntemattomia osuuksia on juoksussa pimeällä yli 15 %, kokeile toista `--suunta`-arvoa tai via-pistettä ja valitse parempi.
5. Jos ajo kaatuu verkkovirheeseen (connect_rejected / 403), älä kokeile kiertoteitä. Kerro kerran, että claude.ai:n selainversiossa kohdassa Asetukset → Kyvykkyydet pitää sallia verkkotunnukset `brouter.de` ja `nominatim.openstreetmap.org`.
6. Jos BRouter palauttaa profiilivirheen, korjaa kyseinen profiilirivi virheilmoituksen mukaan ja aja uudelleen. Mainitse korjaus lopuksi yhdellä rivillä.

## Toimita

- Lähetä GPX `SendUserFile`-työkalulla (`display: "attach"`, `status: "normal"`).
- Vastaa lyhyesti suomeksi: matka, nousu, valaistus- ja pintajakauma, mahdolliset pimeät pätkät (km-kohdat) ja muutos tavoitteeseen.
- Siirto-ohje yhdellä rivillä: **Avaa tiedosto puhelimessa → Jaa → Connect → valitse laji (skriptin "Connectissa valitse") → Lähetä laitteeseen.**
- Muistuta, että valaistusarvio perustuu OpenStreetMapin `lit`-merkintöihin: "tuntematon" ei tarkoita pimeää, mutta varmuutta ei ole.

## Skripti (`reitti.py`)

```python
#!/usr/bin/env python3
"""Reittisuunnittelu: Nominatim -> BRouter (oma profiili) -> GPX + raportti."""
import argparse, json, math, os, re, ssl, sys, time, urllib.parse, urllib.request

UA = "reittisuunnittelu-skill/1.0"
BROUTER = "https://brouter.de/brouter"
KESKUS = (62.7903, 22.8403)   # Seinäjoen keskusta; nimihaun osumista valitaan lähin

COMMON_GLOBAL = """---context:global
assign processUnusedTags = true
assign turnInstructionMode = 0
assign downhillcost = 0
assign uphillcost = 0
assign lit_weight = {LIT}
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
assign costfactor = if isblocked then 10000 else multiply basecost multiply surfacefactor litfactor
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
assign costfactor = if isblocked then 10000 else multiply basecost multiply surfacefactor litfactor
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
assign costfactor = if isblocked then 10000 else multiply basecost multiply surfacefactor litfactor
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
assign costfactor = if isblocked then 10000 else multiply basecost multiply surfacefactor litfactor
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
                    else multiply basecost multiply surfacefactor litfactor
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
    with urllib.request.urlopen(req, timeout=60, context=ctx()) as r:
        return r.read().decode("utf-8")

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

def upload_profile(sport, lit):
    _, _, body = PROFILES[sport]
    text = COMMON_GLOBAL.replace("{LIT}", str(lit)) + body + NODE
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

def analyse(feat):
    props = feat["properties"]; total = float(props["track-length"])
    msgs = props.get("messages") or []
    stats = {"lit": {}, "surf": {}, "hw": {}}; stretches = []
    if len(msgs) > 1:
        hdr = msgs[0]; iD = hdr.index("Distance"); iW = hdr.index("WayTags")
        dists = [float(r[iD]) for r in msgs[1:]]
        if abs(sum(dists) - total) > 0.2 * total:   # kumulatiivinen -> erotukset
            dists = [d - (dists[i-1] if i else 0) for i, d in enumerate(dists)]
        pos = 0.0; cur = None
        for r, d in zip(msgs[1:], dists):
            tags = dict(t.split("=", 1) for t in r[iW].split() if "=" in t)
            lit = {"yes": "valaistu", "no": "valaisematon"}.get(tags.get("lit"), "tuntematon")
            s = tags.get("surface", "")
            surf = ("päällystetty" if s in ("asphalt", "paved", "concrete", "paving_stones", "sett")
                    else "päällystämätön" if s else "tuntematon")
            for k, v in (("lit", lit), ("surf", surf), ("hw", tags.get("highway", "muu"))):
                stats[k][v] = stats[k].get(v, 0) + d
            if lit != "valaistu":
                cur = cur or [pos, pos]; cur[1] = pos + d
            elif cur:
                stretches.append(cur); cur = None
            pos += d
        if cur: stretches.append(cur)
    return total, float(props.get("filtered ascend", 0) or 0), stats, stretches

def asciify(s):
    s = s.lower().translate(str.maketrans("äöå", "aoa"))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "reitti"

def write_gpx(feat, name, sport, outdir):
    coords = feat["geometry"]["coordinates"]; km = float(feat["properties"]["track-length"]) / 1000
    fn = os.path.join(outdir, f"{sport}_{asciify(name)}_{km:.1f}km.gpx")
    esc = lambda t: t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    pts = "\n".join(f'      <trkpt lat="{c[1]:.6f}" lon="{c[0]:.6f}">' +
                    (f"<ele>{c[2]:.1f}</ele>" if len(c) > 2 else "") + "</trkpt>" for c in coords)
    gpx = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="reittisuunnittelu" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata><name>{esc(name)}</name></metadata>
  <trk><name>{esc(name)}</name><type>{GPX_TYPE[sport]}</type><trkseg>
{pts}
  </trkseg></trk>
</gpx>
"""
    os.makedirs(outdir, exist_ok=True)
    with open(fn, "w", encoding="utf-8") as f: f.write(gpx)
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
    ap.add_argument("--nimi", default="Reitti")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()

    lit = LIT_LEVELS[a.valaistus] if a.valaistus else PROFILES[a.laji][1]
    pid = upload_profile(a.laji, lit)
    start = geocode(a.lahto); vias = [geocode(v) for v in a.via]
    loop = not a.maali
    if loop and not vias and not a.km: sys.exit("VIRHE: lenkkiin tarvitaan --km tai --via")
    end = start if loop else geocode(a.maali)
    base = [(p[0], p[1]) for p in [start] + vias]

    if loop and not vias:
        r = a.km / 4.7; best = None
        for _ in range(5):
            p1 = dest(start[0], start[1], a.suunta - 30, r); p2 = dest(start[0], start[1], a.suunta + 30, r)
            feat = route([base[0], p1, p2, base[0]], pid)
            km = float(feat["properties"]["track-length"]) / 1000
            if not best or abs(km - a.km) < abs(best[1] - a.km): best = (feat, km)
            if abs(km - a.km) / a.km < 0.06: break
            r *= a.km / km
        feat = best[0]
    else:
        feat = route(base + [(end[0], end[1])], pid)

    total, asc, stats, stretches = analyse(feat)
    fn = write_gpx(feat, a.nimi, a.laji, a.out)
    print(f"TIEDOSTO: {fn}")
    print(f"LAJI: {a.laji} | Connectissa valitse: {CONNECT_LAJI[a.laji]} | valaistuspaino: {lit}")
    print(f"LÄHTÖ: {start[2]}")
    if not loop: print(f"MAALI: {end[2]}")
    print(f"MATKA: {total/1000:.2f} km" + (f" (tavoite {a.km} km)" if a.km else "") + f" | nousu {asc:.0f} m")
    if total:
        print("VALAISTUS: " + pct(stats["lit"], total))
        print("PINTA: " + pct(stats["surf"], total))
        print("TIETYYPIT: " + pct(dict(sorted(stats["hw"].items(), key=lambda x: -x[1])[:5]), total))
        long = sorted([s for s in stretches if s[1] - s[0] > 300], key=lambda s: s[0] - s[1])[:3]
        for s in sorted(long):
            print(f"VAROITUS: ei valaistusmerkintää km {s[0]/1000:.1f}–{s[1]/1000:.1f} ({(s[1]-s[0]):.0f} m)")

if __name__ == "__main__":
    main()
```
