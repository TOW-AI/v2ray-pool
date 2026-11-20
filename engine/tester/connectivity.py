"""Interpret observer probe results as tunnel connectivity evidence."""

from engine.models import ObserverResult


def has_tunnel_connectivity(results: list[ObserverResult]) -> bool:
    """One successful HTTPS probe proves a tunnel path, not IP stability."""
    return any(result.success for result in results)
