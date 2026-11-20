from engine.intelligence.geoip import lookup_country
from engine.intelligence.ip_tracker import append_observations


def test_geoip_returns_unknown_without_database():
    assert lookup_country(None) == {
        "country_code": None,
        "country_name": None,
        "geoip_checked_at": None,
    }
    assert lookup_country("8.8.8.8", "/not/a/real/geoip/database.mmdb")["country_code"] is None


def test_ip_tracker_appends_once_per_family_and_run():
    ledger = []
    result = {
        "config_id": "sha256:config",
        "run_id": "run-1",
        "finished_at": "2026-11-20T12:00:00Z",
        "ip_observation": {
            "ipv4": {
                "ip": "8.8.8.8",
                "observers": [{"observer_id": "one", "ip": "8.8.8.8"}],
                "consensus": True,
                "result_code": "OK",
            }
        },
    }
    assert append_observations(ledger, result) == 1
    assert append_observations(ledger, result) == 0
    assert len(ledger) == 1
    assert ledger[0]["ip_family"] == "ipv4"
    assert ledger[0]["observation_id"]
