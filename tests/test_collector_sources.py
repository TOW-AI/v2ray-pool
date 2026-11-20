import threading
import time

from engine.collector import sources as source_module
UUID = "123e4567-e89b-12d3-a456-426614174000"


def test_source_collection_respects_concurrency_and_keeps_order(monkeypatch):
    lock = threading.Lock()
    current = 0
    maximum = 0

    def fake_fetch(source, _settings):
        nonlocal current, maximum
        with lock:
            current += 1
            maximum = max(maximum, current)
        time.sleep(0.03)
        with lock:
            current -= 1
        uri = f"vless://{UUID}@{source['source_id']}.example:443"
        return uri.encode(), {"status_code": 200, "bytes": len(uri), "redirects": 0, "resolved_ip": "93.184.216.34"}

    monkeypatch.setattr(source_module, "fetch_source", fake_fetch)
    items = [
        {
            "source_id": f"source-{index}",
            "enabled": True,
            "public_redistribution": True,
            "priority": 0,
            "format": "plain",
        }
        for index in range(4)
    ]
    result, report = source_module.collect_sources(items, {"max_concurrency": 2})
    assert len(result) == 4
    assert 2 <= maximum <= 2
    assert [item["source_id"] for item in report["sources"]] == [
        "source-0", "source-1", "source-2", "source-3"
    ]
    assert report["sources_succeeded"] == 4


def test_source_without_public_redistribution_is_not_fetched(monkeypatch):
    def forbidden_fetch(*_args, **_kwargs):
        raise AssertionError("Private sources must not be fetched.")

    monkeypatch.setattr(source_module, "fetch_source", forbidden_fetch)
    items = [{
        "source_id": "private-source",
        "enabled": True,
        "public_redistribution": False,
        "priority": 0,
        "format": "plain",
    }]
    result, report = source_module.collect_sources(items, {"max_concurrency": 1})
    assert result == []
    assert report["sources_failed"] == 1
    assert report["sources"][0]["error_code"] == "SOURCE_NOT_APPROVED_FOR_PUBLIC_REDISTRIBUTION"
