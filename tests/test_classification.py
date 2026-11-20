from datetime import UTC, datetime, timedelta

from engine.intelligence.classification import classify_config

POLICY = {
    "fixed_candidate": {"min_runs": 3, "min_span_hours": 24},
    "fixed_verified": {"min_runs": 6, "min_span_hours": 72},
    "rotating": {"min_runs": 2, "min_distinct_ips": 2},
    "fixed_evidence_max_age_hours": 168,
    "required_ip_families": ["ipv4"],
}
NOW = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
RECORD = {"validation": {"status": "VALID"}, "last_test_at": "2026-01-10T10:00:00Z", "last_connectivity": "connected"}


def observation(run, hours_ago, ip="93.184.216.34", family="ipv4", consensus=True, code="CONSENSUS"):
    timestamp = (NOW - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")
    return {
        "run_id": run,
        "observed_at": timestamp,
        "ip_family": family,
        "ip": ip if consensus else None,
        "consensus": consensus,
        "observers": [
            {"observer_id": "a", "success": True, "ip_family": family, "ip": ip if consensus else None},
            {"observer_id": "b", "success": True, "ip_family": family, "ip": ip if consensus else None},
        ],
        "result_code": code,
    }


def test_one_run_with_many_observers_is_not_fixed():
    data = [observation("run-1", 48), observation("run-1", 48)]
    result = classify_config(RECORD, data, POLICY, NOW)
    assert result["overall"] == "IP_UNVERIFIED"
    assert result["ipv4"]["run_count"] == 1


def test_three_independent_runs_over_one_day_are_candidate():
    data = [observation("run-1", 30), observation("run-2", 18), observation("run-3", 6)]
    result = classify_config(RECORD, data, POLICY, NOW)
    assert result["overall"] == "FIXED_CANDIDATE"
    assert result["ipv4"]["run_count"] == 3


def test_six_runs_over_three_days_are_verified():
    data = [observation(f"run-{index}", hours) for index, hours in enumerate([80, 64, 48, 32, 16, 4])]
    result = classify_config(RECORD, data, POLICY, NOW)
    assert result["overall"] == "FIXED_VERIFIED"
    assert result["ipv4"]["span_hours"] == 76


def test_two_independent_ips_are_rotating():
    data = [observation("run-1", 20, "93.184.216.34"), observation("run-2", 4, "1.1.1.1")]
    result = classify_config(RECORD, data, POLICY, NOW)
    assert result["overall"] == "ROTATING"
    assert result["ipv4"]["change_count"] == 1
    assert result["ipv4"]["last_ip_change_at"] is not None


def test_observer_disagreement_is_not_rotating():
    data = [observation("run-1", 2, consensus=False, code="OBSERVER_DISAGREEMENT")]
    result = classify_config(RECORD, data, POLICY, NOW)
    assert result["overall"] == "IP_UNVERIFIED"
    assert "OBSERVER_DISAGREEMENT" in result["classification_reason_codes"]


def test_old_evidence_is_not_verified():
    data = [observation(f"run-{index}", 200 + index) for index in range(6)]
    result = classify_config(RECORD, data, POLICY, NOW)
    assert result["overall"] == "IP_UNVERIFIED"
    assert "EVIDENCE_EXPIRED" in result["classification_reason_codes"]


def test_ipv4_and_ipv6_are_classified_separately():
    data = [
        observation(f"v4-{index}", hours, "93.184.216.34", "ipv4")
        for index, hours in enumerate([80, 64, 48, 32, 16, 4])
    ]
    data.extend([
        observation("v6-1", 20, "2001:4860:4860::8888", "ipv6"),
        observation("v6-2", 4, "2606:4700:4700::1111", "ipv6"),
    ])
    result = classify_config(RECORD, data, POLICY, NOW)
    assert result["ipv4"]["status"] == "FIXED_VERIFIED"
    assert result["ipv6"]["status"] == "ROTATING"
    assert result["overall"] == "FIXED_VERIFIED"


def test_recent_observer_disagreement_suspends_previous_fixed_claim():
    data = [observation(f"run-{index}", hours) for index, hours in enumerate([80, 64, 48, 32, 16, 4])]
    data.append(observation("run-7", 1, consensus=False, code="OBSERVER_DISAGREEMENT"))
    result = classify_config(RECORD, data, POLICY, NOW)
    assert result["overall"] == "IP_UNVERIFIED"
    assert result["ipv4"]["status"] == "IP_UNVERIFIED"
    assert "OBSERVER_DISAGREEMENT" in result["classification_reason_codes"]


def test_fixed_status_can_be_reverified_after_a_fresh_stable_window():
    data = [
        observation("old-1", 160, "93.184.216.34"),
        observation("old-2", 144, "93.184.216.34"),
        observation("old-3", 128, "1.1.1.1"),
    ]
    data.extend(
        observation(f"new-{index}", hours, "1.1.1.1")
        for index, hours in enumerate([80, 64, 48, 32, 16, 4])
    )
    result = classify_config(RECORD, data, POLICY, NOW)
    assert result["overall"] == "FIXED_VERIFIED"
    assert result["ipv4"]["ip"] == "1.1.1.1"
    assert result["ipv4"]["run_count"] == 7


def test_latest_failed_connection_does_not_keep_fixed_verified_status():
    data = [observation(f"run-{index}", hours) for index, hours in enumerate([80, 64, 48, 32, 16, 4])]
    record = {**RECORD, "last_connectivity": "failed"}
    result = classify_config(record, data, POLICY, NOW)
    assert result["ipv4"]["status"] == "FIXED_VERIFIED"
    assert result["overall"] == "UNSTABLE"
    assert "CONNECTION_FAILED" in result["classification_reason_codes"]


def test_conflicting_observations_in_one_run_reset_fixed_evidence_window():
    data = [
        observation(f"run-{index}", hours)
        for index, hours in enumerate([100, 80, 60, 32, 16, 4])
    ]
    data.append(observation("conflict-run", 50, "93.184.216.34"))
    data.append(observation("conflict-run", 50, "1.1.1.1"))

    result = classify_config(RECORD, data, POLICY, NOW)
    assert result["overall"] == "FIXED_CANDIDATE"
    assert result["ipv4"]["run_count"] == 3
    assert result["ipv4"]["span_hours"] == 28
