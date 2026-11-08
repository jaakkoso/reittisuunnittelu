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

1. Hae uusin skripti GitHubista ja aja se Bashilla, esim.:
   ```
   curl -fsSL -o reitti.py https://raw.githubusercontent.com/jaakkoso/reittisuunnittelu/main/reitti.py
   python3 reitti.py --laji juoksu-katu --lahto "62.79,22.84" --km 7 --suunta 270 --valaistus vahva --nimi "Iltalenkki" --out .
   python3 reitti.py --laji gravel --lahto "Seinäjoen asema" --maali "Ilmajoen kirkko" --via "Ahonkylä, Ilmajoki" --nimi "Gravel Ilmajoelle" --out .
   ```
   Hae skripti kerran keskustelua kohden. Jos `reitti.py` on jo työhakemistossa tästä keskustelusta, käytä sitä.
2. Tarkista tulosteen LÄHTÖ- ja MAALI-rivit. Nimihaku (Nominatim) valitsee osumista Seinäjoen keskustaa lähimmän, mutta voi silti osua väärään paikkaan (esim. "rautatieasema" → Ylistaro). Jos paikka on väärä tai haku ei löydä mitään (esim. "Virkistysuimala Pore"), kokeile toista nimeä ("Seinäjoen asema") tai osoitetta, tai hae paikan osoite/koordinaatit verkkohaulla ja anna `lat,lon`.
3. Lenkissä skripti leikkaa umpikujapistot pois ja vaihtaa tarvittaessa suuntaa, jotta pituus osuu tavoitteeseen. Jos tulosteessa on `SUUNTA:`-rivi, pyydetty suunta oli umpikujaseutua ja lenkki lähtee toiseen suuntaan. Kerro tämä käyttäjälle.
4. A→B-reitissä: jos matka jää tavoitteesta yli 10 % lyhyeksi, lisää `--via`-piste reitin sivuun ja aja uudelleen (enintään 3 kertaa). Jos tulosteessa on `HUOM:` umpikujapistoista, kokeile via-pistettä, joka ohjaa reitin läpikulkevalle tielle.
5. Jos raportissa valaisemattomia/tuntemattomia osuuksia on juoksussa pimeällä yli 15 %, kokeile toista `--suunta`-arvoa tai via-pistettä ja valitse parempi.
6. Verkkovirheet (connect_rejected / 403 / curl-virhe):
   - Jos skriptin haku GitHubista epäonnistuu, kerro kerran, että claude.ai:n selainversiossa kohdassa Asetukset → Kyvykkyydet pitää sallia `raw.githubusercontent.com`.
   - Jos BRouter tai Nominatim estää yhteyden, kerro kerran, että sallittuihin verkkotunnuksiin pitää lisätä `brouter.de` ja `nominatim.openstreetmap.org`.
   - Jos skripti tulostaa `VIRHE: brouter.de vastasi 403 … käyttöraja`, BRouterin julkinen palvelin rajoittaa kutsuja. Kerro se ja ehdota uutta yritystä hetken päästä.
   - Älä kokeile kiertoteitä.
7. Jos BRouter palauttaa profiilivirheen, kerro virheilmoitus käyttäjälle. Älä muokkaa skriptiä: profiilit korjataan repossa Claude Codella.

## Toimita

1. **Näytä esikatselu aina ensin.** Lue tulosteen `ESIKATSELU:`-rivin SVG-tiedosto ja näytä se `show_widget`-työkalulla ennen GPX:n lähettämistä. Värit kertovat valaistuksen (tai pinnan, jos valaistuspaino on 0) legendan mukaan.
2. Lähetä GPX (`TIEDOSTO:`-rivi) `SendUserFile`-työkalulla (`display: "attach"`, `status: "normal"`).
3. Vastaa lyhyesti suomeksi: matka, nousu, valaistus- ja pintajakauma, mahdolliset pimeät pätkät (km-kohdat), muutos tavoitteeseen ja vaihtunut suunta (`SUUNTA:`).
4. Siirto-ohje yhdellä rivillä: **Avaa tiedosto puhelimessa → Jaa → Connect → valitse laji (skriptin "Connectissa valitse") → Lähetä laitteeseen.**
5. Muistuta, että valaistusarvio perustuu OpenStreetMapin `lit`-merkintöihin: "tuntematon" ei tarkoita pimeää, mutta varmuutta ei ole.
