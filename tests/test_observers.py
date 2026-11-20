from engine.tester import observers


class FakeResponse:
    def __init__(self, body: bytes, status_code: int = 200, headers=None):
        self.body = body
        self.status_code = status_code
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP failure")

    def iter_content(self, chunk_size=1024):
        yield self.body


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.trust_env = True
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_observer_uses_family_specific_url_and_socks_proxy(monkeypatch):
    session = FakeSession(FakeResponse(b"{\"ip\":\"93.184.216.34\"}"))
    monkeypatch.setattr(observers.requests, "Session", lambda: session)
    results = observers.query_observers(
        [{
            "id": "ipify",
            "url_ipv4": "https://api.ipify.org?format=json",
            "url_ipv6": "https://api6.ipify.org?format=json",
            "response_format": "json",
            "response_field": "ip",
        }],
        10080,
        5,
        family="ipv4",
    )
    assert results[0].success is True
    assert results[0].ip_family == "ipv4"
    url, options = session.calls[0]
    assert url.startswith("https://api.ipify.org")
    assert options["proxies"]["https"] == "socks5h://127.0.0.1:10080"
    assert options["allow_redirects"] is False
    assert options["stream"] is True


def test_family_mismatch_is_rejected(monkeypatch):
    session = FakeSession(FakeResponse(b"2001:4860:4860::8888"))
    monkeypatch.setattr(observers.requests, "Session", lambda: session)
    results = observers.query_observers(
        [{"id": "v4", "url_ipv4": "https://observer.example/ip", "response_format": "text"}],
        10080,
        5,
        family="ipv4",
    )
    assert results[0].success is False
    assert results[0].error_code == "OBSERVER_FAMILY_MISMATCH"


def test_oversized_observer_response_is_rejected(monkeypatch):
    session = FakeSession(FakeResponse(b"93.184.216.34", headers={"Content-Length": "5000"}))
    monkeypatch.setattr(observers.requests, "Session", lambda: session)
    results = observers.query_observers(
        [{"id": "v4", "url_ipv4": "https://observer.example/ip", "response_format": "text"}],
        10080,
        5,
        family="ipv4",
    )
    assert results[0].success is False
    assert results[0].error_code == "OBSERVER_RESPONSE_TOO_LARGE"


def test_local_observer_endpoint_is_blocked_without_network(monkeypatch):
    def forbidden_session():
        raise AssertionError("A local observer URL must be rejected before HTTP access.")

    monkeypatch.setattr(observers.requests, "Session", forbidden_session)
    results = observers.query_observers(
        [{"id": "local", "url_ipv4": "https://127.0.0.1/ip", "response_format": "text"}],
        10080,
        5,
        family="ipv4",
    )
    assert results[0].success is False
    assert results[0].error_code == "OBSERVER_URL_BLOCKED"
