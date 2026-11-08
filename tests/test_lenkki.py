"""Lenkkilogiikan testit. Ei verkkoa: BRouter-vastaukset tulevat fixtures-kansiosta."""
import gzip, json, os, sys, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import reitti as R

def P(*coords):
    """Pisteet (lon, lat) asteina -> attach()-muotoiset (koordinaatti, tagit)."""
    return [([lon, lat], {}) for lon, lat in coords]

A, B, C, D, T = (22.80, 62.79), (22.81, 62.79), (22.82, 62.79), (22.82, 62.80), (22.81, 62.80)

class TrimSpurs(unittest.TestCase):
    def test_leikkaa_piston(self):
        # A-B-T-B-C: pisto B->T->B pois
        self.assertEqual(R.trim_spurs(P(A, B, T, B, C)), P(A, B, C))

    def test_pitka_pisto(self):
        # A-B-C-D-C-B-T: pisto kääntyy D:ssä ja palaa B:hen asti
        self.assertEqual(R.trim_spurs(P(A, B, C, D, C, B, T)), P(A, B, T))

    def test_sisakkaiset_pistot(self):
        # A-B-C-D-C-T-C-B-A2: ensin C-D-C pois, sitten paljastuu C-T-C, sitten B-C-B
        A2 = (22.79, 62.79)
        self.assertEqual(R.trim_spurs(P(A2, A, B, C, D, C, T, C, B, A)), P(A2, A))

    def test_ehja_lenkki_ennallaan(self):
        loop = P(A, B, C, D, T, A)
        self.assertEqual(R.trim_spurs(loop), loop)

    def test_tagit_sailyvat(self):
        pts = [([*A], {"lit": "yes"}), ([*B], {"lit": "no"}), ([*T], {}), ([*B], {}), ([*C], {"lit": "yes"})]
        self.assertEqual([t for _, t in R.trim_spurs(pts)], [{"lit": "yes"}, {"lit": "no"}, {"lit": "yes"}])

class Fixture:
    """Toistaa tallennetut BRouter-vastaukset pistelistan perusteella."""
    def __init__(self, name):
        with gzip.open(os.path.join(HERE, "fixtures", name), "rt", encoding="utf-8") as f:
            self.calls = {json.dumps(c["points"]): c["feature"] for c in json.load(f)}
        self.n = 0

    def route(self, points, pid):
        self.n += 1
        k = json.dumps([[round(a, 6), round(b, 6)] for a, b in points])
        if k not in self.calls: raise AssertionError(f"ei tallennettua vastausta: {k}")
        return self.calls[k]

class LoopRoute(unittest.TestCase):
    START = (62.7907384, 22.8437886)   # Seinäjoen asema

    def test_umpikujasuunta_osuu_tavoitteeseen(self):
        """Regressio: 6 km pohjoiseen antoi 3,63 km, koska fix_vias() veti kääntöpisteet aina
        samoihin liittymiin. Nyt pistot leikataan ja suunta vaihdetaan."""
        fx = Fixture("juoksu-katu_asema_6km_suunta0.json.gz")
        with mock.patch.object(R, "route", fx.route):
            pts, ln, suunta = R.loop_route(self.START, 6.0, 0, "custom_test")
        self.assertLess(abs(ln / 1000 - 6.0) / 6.0, 0.07)
        self.assertLessEqual(fx.n, R.LOOP_TRIES)
        self.assertEqual(R.spurs(pts), [])
        self.assertEqual(R.key(*pts[0][0][:2]), R.key(*pts[-1][0][:2]))   # lenkki palaa lähtöön
        self.assertAlmostEqual(ln, R.length(pts))

if __name__ == "__main__":
    unittest.main()
