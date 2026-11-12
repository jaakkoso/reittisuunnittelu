# Reittisuunnittelu

Työkalu, joka tekee lenkkireitin GPX-tiedostoksi Garmin Connectiin ja sieltä Fenixiin. Jaakko tilaa reitit puhelimella Claude-sovelluksesta (skilli `reittisuunnittelu`), saa esikatselun ja GPX:n ja jakaa sen Connectiin. Kehitys tehdään tässä kansiossa Claude Codella.

## Työnjako

- **Claude Code (tämä kansio):** skriptin `reitti.py` ja reititysprofiilien kehitys, testit, versionhallinta.
- **Claude-sovellus (chat):** reittien tilaaminen, esikatselut ja muokkaukset. Skilli ajaa `reitti.py`:n pilvikontissa.

## Arkkitehtuuri

`reitti.py` (vain Python stdlib):
1. Geokoodaus: Nominatim (`countrycodes=fi`, 8 osumaa, valitaan lähin Seinäjoen keskustaa `KESKUS`). Hyväksyy myös `lat,lon`.
2. Reititysprofiili: lajikohtainen BRouter-profiili (.brf-teksti `PROFILES`-sanakirjassa) ladataan POST `https://brouter.de/brouter/profile` → `custom_...`-id. `lit_weight` (0/1/2) ja `quiet_weight` (0/1, `--hiljainen`) korvataan globaaliin kontekstiin. `quietfactor` kertoo kustannuksen BRouterin arvioidulla melulla (`estimated_noise_class` 3–6 → ×1,15–2,2) ja metsäisyydellä (`estimated_forest_class` 2+ → ×0,93/0,85).
3. Reititys: GET `https://brouter.de/brouter?lonlats=...&profile=<id>&format=geojson`. `messages`-taulun `WayTags` sisältää OSM-tagit (lit, surface, highway). Longitude/Latitude ovat mikroasteina ja vastaavat geometrian koordinaatteja tarkasti.
4. Lenkki (ei maalia): kolmio lähtö → p1 → p2 → lähtö, kääntöpisteet etäisyydellä r suuntiin `suunta ± 30°`. Alkuarvio `r = km / 4.7`, skaalataan `r *= tavoite / toteutunut` enintään 6 kertaa, kunnes ±6 %.
5. Analyysi: valaistus- ja pintajakauma, ympäristö (`YMPÄRISTÖ:` meluisa/metsäinen/muu), tietyypit, yli 300 m valaisemattomat/tuntemattomat pätkät km-kohtineen, nousu (3 m hystereesi).
6. Tulosteet: GPX 1.1 (`<type>` lajin mukaan, ASCII-tiedostonimi `laji_nimi_X.Xkm.gpx`), esikatselu (`..._esikatselu.html`: 380 px SVG, värit valaistuksen tai pinnan mukaan, mittakaava, legenda) chatin show_widget-työkalulle ja karttasivu (`..._kartta.html`, `write_map()`, rivi `KARTTA:`) Artifact-julkaisuun. Karttasivu upottaa OSM-tiilet (`tile.openstreetmap.org`, zoom joka mahtuu ~640×820 px:iin + yksi tarkempi) data-URI:na, koska artifaktin CSP estää ulkoiset kuvat; reitti valkoisella reunalla, km-merkit, lähtö/maali, "Koko reitti" / vieritettävä "Tarkka" -näkymä, tilastot. Jos tiiliä ei saada, sivu tehdään ilman pohjakarttaa. Google Maps -nappi poistettu 12.11.2026 (Maps laski välit itse ja näytti olemattomia pistoja); `maps_url()` on jäljellä mutta ei käytössä.

Lajit: `juoksu-katu`, `juoksu-maasto`, `gravel`, `xc-mtb`, `rullaluistelu` (enduro → xc-mtb).

## Todennettu (8.11.2026)

- Kaikki viisi profiilia menevät BRouterin profiilivalidoinnista läpi.
- Juoksu-katu-lenkki Seinäjoen asemalta 6 km → 6,1 km, valaistu 64 %. Rullaluistelu Kyrkösjärveltä: 87 % päällystettyä pyörätietä.
- Gravel Seinäjoen asema → Ilmajoen kirkko: 21,1 km, 52 % päällystämätöntä.
- `--hiljainen` Ilmolantie → Ukkoherranlenkki (juoksu-maasto): meluisaa 0 % (ilman 1 %; juoksu-katu-profiililla 15 %), 7,4 km, päällystämätöntä 31 %. Rullaluistelussa vaikutus pieni, koska asfalttiväylät kulkevat teiden varsilla (meluisaa 33 %).
- Nimihaku osui aluksi Ylistaroon ("rautatieasema") → korjattu `KESKUS`-valinnalla. Nominatim ei löydä "Virkistysuimala Pore".

## Kesken / tiedossa olevat ongelmat

1. **Umpikujapistot lenkeissä – KORJATTU 8.11.2026.** Syy: "pistot" olivat 1–7 km edestakaisia osuuksia (asemalta pohjoiseen ei läpikulkevaa tieverkkoa), ja `fix_vias()` veti kääntöpisteet joka kierroksella samoihin liittymiin → aina 3,63 km r:stä riippumatta. Nyt `loop_route()`: `trim_spurs()` leikkaa pistot geometriasta, `r` skaalataan leikatun pituuden mukaan, ja jos leikattavaa on yli 30 %, kokeillaan seuraavaa suuntaa (`LOOP_TURNS`, enintään `LOOP_TRIES` = 12 BRouter-kutsua). Vaihtunut suunta tulostetaan rivillä `SUUNTA:`. Asemalta 6 km: 5,7–6,4 km kaikkiin suuntiin, mutta pyydetty suunta vaihtuu usein 60–90°. Testit: `python3 -m unittest discover -s tests`.
2. Valaistustieto on vain niin hyvä kuin OSM:n `lit`-merkinnät. "Tuntematon" ≠ pimeä.
3. Connectin GPX-tuonti puhelimen jakovalikon kautta on testaamatta.
4. BRouterin julkisella palvelimella on käyttörajat. Vaihtoehto: oma BRouter-palvelin Mac minillä (Docker/OrbStack), Suomen segmenttitiedostot.

## Seuraavat askeleet

1. Korjaa kohta 1 ja lisää testit (`tests/`, tallennetut BRouter-vastaukset fixtureina, ei verkkoa testeissä).
2. ~~Vie repo GitHubiin~~ – tehty 8.11.2026: https://github.com/jaakkoso/reittisuunnittelu (julkinen). Skripti: `https://raw.githubusercontent.com/jaakkoso/reittisuunnittelu/main/reitti.py`. Nyt chat-skilli voi hakea uusimman `reitti.py`:n repolta (GitHub on pilvikontin sallituissa verkkotunnuksissa) eikä skriptiä tarvitse upottaa SKILL.md:hen.
3. ~~Päivitä skilli~~ – tehty 8.11.2026: `skill/SKILL.md` hakee `reitti.py`:n GitHubin raw-osoitteesta (ei upotettua skriptiä), näyttää esikatselun aina ennen GPX:ää ja kertoo `SUUNTA:`-rivin. Skilli pitää ladata Claude-sovellukseen käsin (zip `skill/`-kansiosta), kun SKILL.md muuttuu; pelkkä `reitti.py`:n muutos riittää pushata.

## Ajo

```
python3 reitti.py --laji juoksu-katu --lahto "Seinäjoen asema" --km 6 --valaistus vahva --nimi "Iltalenkki" --out out
python3 reitti.py --laji gravel --lahto "Seinäjoen asema" --maali "Ilmajoen kirkko" --nimi "Gravel Ilmajoelle" --out out
```

Verkkotunnukset: `brouter.de`, `nominatim.openstreetmap.org`, `tile.openstreetmap.org` (karttasivun pohjakartta, User-Agent pakollinen). Nominatim: max 1 pyyntö/s, User-Agent `reittisuunnittelu-skill/1.0`.
