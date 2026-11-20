import base64
import json

from engine.collector.parser import parse_uri
from engine.core.state import StateStore
from engine.distribution.api import build_api
from engine.distribution.quality import validate_data_tree
from engine.distribution.subscriptions import write_subscriptions
from engine.intelligence.ranking import build_rankings
from engine.models import iso_utc

UUID = "123e4567-e89b-12d3-a456-426614174000"


def record(uri: str, status: str, public: bool, country: str | None = None) -> dict:
    parsed = parse_uri(uri)
    return {
        "config_id": parsed.config_id,
        "protocol": parsed.protocol,
        "uri": uri,
        "public_redistribution": public,
        "status": status,
        "country_code": country,
        "country_name": "Test Country" if country else None,
        "geoip_checked_at": iso_utc() if country else None,
        "ip_status": {
            "overall": status,
            "ipv4": {"status": status if status in {"FIXED_CANDIDATE", "FIXED_VERIFIED"} else "IP_UNVERIFIED", "ip": "93.184.216.34" if status in {"FIXED_CANDIDATE", "FIXED_VERIFIED"} else None, "run_count": 6, "observer_count": 2, "first_observed_at": iso_utc(), "last_observed_at": iso_utc(), "span_hours": 80.0, "distinct_ips": ["93.184.216.34"], "change_count": 0, "last_ip_change_at": None},
            "ipv6": {"status": "IP_UNVERIFIED", "ip": None, "run_count": 0, "observer_count": 0, "first_observed_at": None, "last_observed_at": None, "span_hours": 0.0, "distinct_ips": [], "change_count": 0, "last_ip_change_at": None},
        },
        "metrics": {"latency_ms": 80, "throughput_bps": None, "measured_at": iso_utc()},
        "connection_success_ratio": 1.0,
        "eligible_scheduled_checks": 1,
        "successful_scheduled_checks": 1,
        "last_test_at": iso_utc(),
    }


def decode_file(path, encoding="base64"):
    raw = path.read_bytes()
    if not raw:
        return []
    if encoding == "base64":
        raw = base64.b64decode(raw, validate=True)
    return raw.decode().splitlines()


def test_subscriptions_exclude_private_and_unpublishable_records(tmp_path):
    fixed_uri = f"vless://{UUID}@one.example:443#fixed"
    rotating_uri = f"trojan://password@two.example:443#rotating"
    private_uri = f"vless://{UUID}@private.example:443#private"
    invalid_uri = f"ss://Y2hhY2hhMjAtaWV0Zi1wb2x5MTMwNTpwYXNzQGV4YW1wbGUuY29tOjgzODg=#invalid"
    configs = {
        parse_uri(fixed_uri).config_id: record(fixed_uri, "FIXED_VERIFIED", True, "US"),
        parse_uri(rotating_uri).config_id: record(rotating_uri, "ROTATING", True),
        parse_uri(private_uri).config_id: record(private_uri, "FIXED_VERIFIED", False, "US"),
        parse_uri(invalid_uri).config_id: record(invalid_uri, "INVALID", True, "US"),
    }
    rankings = {
        "fixed": [{"config_id": parse_uri(fixed_uri).config_id}],
        "rotating": [{"config_id": parse_uri(rotating_uri).config_id}],
        "fastest": [],
        "balanced": [
            {"config_id": parse_uri(fixed_uri).config_id},
            {"config_id": parse_uri(rotating_uri).config_id},
        ],
    }
    write_subscriptions(
        tmp_path,
        configs,
        rankings,
        {
            "encoding": "base64",
            "include_rotating_in_main": True,
            "include_unstable_in_main": False,
            "max_top_configs": 50,
        },
    )

    main = decode_file(tmp_path / "sub" / "main.txt")
    fixed_verified = decode_file(tmp_path / "sub" / "fixed-verified.txt")
    protocol_vless = decode_file(tmp_path / "sub" / "protocol" / "vless.txt")
    country_us = decode_file(tmp_path / "sub" / "country" / "US.txt")
    assert main == [fixed_uri, rotating_uri]
    assert fixed_verified == [fixed_uri]
    assert protocol_vless == [fixed_uri]
    assert country_us == [fixed_uri]


def test_rankings_exclude_unapproved_configs():
    private_uri = f"vless://{UUID}@one.example:443"
    public_uri = f"vless://{UUID}@two.example:443"
    private = record(private_uri, "FIXED_VERIFIED", False)
    public = record(public_uri, "FIXED_VERIFIED", True)
    for item in (private, public):
        item["ip_status"] = {"overall": "FIXED_VERIFIED"}
    policy = {
        "max_metric_age_hours": 24,
        "minimum_score_coverage": 0.5,
        "fixed_weights": {"ip_stability": 1.0},
        "rotating_weights": {"connection_success": 1.0},
        "balanced_weights": {"connection_success": 1.0},
    }
    result = build_rankings({private["config_id"]: private, public["config_id"]: public}, policy)
    assert [item["config_id"] for item in result["fixed"]] == [public["config_id"]]
    assert [item["config_id"] for item in result["balanced"]] == [public["config_id"]]
    assert not result["fastest"] or all(item["config_id"] == public["config_id"] for item in result["fastest"])


def test_static_api_filters_private_and_reports_run_success_correctly(tmp_path):
    public_uri = f"vless://{UUID}@public.example:443"
    private_uri = f"trojan://password@private.example:443"
    public = record(public_uri, "FIXED_VERIFIED", True)
    private = record(private_uri, "FIXED_VERIFIED", False)
    configs = {public["config_id"]: public, private["config_id"]: private}
    rankings = {"fixed": [], "rotating": [], "fastest": [], "balanced": []}
    build_api(
        tmp_path,
        configs,
        [],
        rankings,
        "run-test",
        publish_raw_uri=False,
        test_summary={"successful": 0, "failed": 0, "skipped": 2},
    )
    payload = json.loads((tmp_path / "api/v1/configs.json").read_text())
    stats = json.loads((tmp_path / "api/v1/stats.json").read_text())
    assert [item["config_id"] for item in payload["configs"]] == [public["config_id"]]
    assert "uri" not in payload["configs"][0]
    assert stats["freshness"]["last_successful_run_at"] is None


def test_quality_gate_checks_empty_subscription_and_api_tree(tmp_path):
    uri = f"vless://{UUID}@public.example:443"
    item = record(uri, "FIXED_VERIFIED", True)
    configs = {item["config_id"]: item}
    rankings = {"fixed": [], "rotating": [], "fastest": [], "balanced": []}
    build_api(tmp_path, configs, [], rankings, "run-test", False)
    StateStore.save(
        {"configs": configs, "observations": [], "transitions": [], "metrics": {}},
        tmp_path,
    )
    write_subscriptions(
        tmp_path,
        configs,
        rankings,
        {
            "encoding": "base64",
            "include_rotating_in_main": False,
            "include_unstable_in_main": False,
            "max_top_configs": 50,
        },
    )
    report = validate_data_tree(tmp_path, {"subscription": {"encoding": "base64"}}, configs)
    assert report["quality_gate"] == "passed"
