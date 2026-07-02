from app.geo import haversine_m, local_day_key, previous_day_key


def test_haversine_zero_distance():
    assert haversine_m(-1.2795, 36.8163, -1.2795, 36.8163) == 0


def test_haversine_known_distance():
    # ~111m per 0.001 degrees of latitude at the equator
    d = haversine_m(0.0, 36.0, 0.001, 36.0)
    assert 110 < d < 112


def test_haversine_campus_scale():
    # Two points ~150m apart on a campus should not be within a 75m geofence
    d = haversine_m(-1.2795, 36.8163, -1.2782, 36.8163)
    assert d > 75


def test_previous_day_key():
    assert previous_day_key("2026-07-02") == "2026-07-01"
    assert previous_day_key("2026-01-01") == "2025-12-31"


def test_local_day_key_format():
    assert len(local_day_key()) == 10
