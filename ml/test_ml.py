import numpy as np
from ml import patches as P


def test_plane_patch_geometry_and_descriptors():
    # Synthetic Moon-sized mosaic: elevation rises 1000 m per degree of longitude eastward.
    ppd = 64
    lon = (np.arange(360 * ppd) + 0.5) / ppd
    z = np.tile((lon * 1000).astype(np.float32), (180 * ppd, 1))
    m = P.Mosaic(z, 90.0, 0.0, ppd, wrap=True)
    lat0, lon0 = np.array([0.0, 30.0]), np.array([10.0, 20.0])
    la, lo = P.patch_coords("moon", lat0, lon0)
    d = P.descriptors(m.sample(la, lo))
    expected = np.degrees(np.arctan(1000 / (P.RADIUS_M["moon"] * np.pi / 180)))
    assert abs(d["slope_q"][0, 9] - expected) < 0.05
    assert d["rough_rms"][0] < 1.0 and d["valid_frac"].min() == 1.0
    assert abs(d["elev_mean"][0] - 10000) < 5


def test_ids_roundtrip_and_split_is_deterministic():
    ids = np.array([0, 5, 99, 4147199])
    assert (P.decode_ids(P.encode_ids(ids, 4147200), 4147200) == ids).all()
    lat, lon = np.array([18.4, 18.6, -45.0]), np.array([77.7, 77.9, 10.0])
    s = P.split_of("mars", lat, lon)
    assert s[0] == s[1] and (s == P.split_of("mars", lat, lon)).all()
