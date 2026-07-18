"""Tests for the Frankfurter FX cross-rate matrix (offline, mocked)."""

from __future__ import annotations

import json

import pytest
import responses

from edgar import fx

# Captured from live api.frankfurter.dev/v1/latest on 2026-07-17.
SAMPLE = {
    "amount": 1.0,
    "base": "USD",
    "date": "2026-07-17",
    "rates": {"EUR": 0.87451, "GBP": 0.74419, "JPY": 162.35},
}


@pytest.fixture(autouse=True)
def reset_module_cache():
    fx._cache = (0.0, [], {})
    yield
    fx._cache = (0.0, [], {})


@responses.activate
def test_matrix_derives_cross_rates_from_usd_base():
    responses.get(
        fx.FRANKFURTER_URL, body=json.dumps(SAMPLE),
        content_type="application/json",
    )
    result = fx.get_fx_matrix(currencies=["USD", "EUR", "JPY"])
    assert result["date"] == "2026-07-17"
    assert result["currencies"] == ["USD", "EUR", "JPY"]
    assert result["matrix"]["USD"]["USD"] == 1.0
    assert result["matrix"]["USD"]["EUR"] == pytest.approx(0.87451)
    # Cross rate: EUR->JPY = (JPY per USD) / (EUR per USD)
    assert result["matrix"]["EUR"]["JPY"] == pytest.approx(162.35 / 0.87451)
    # And the inverse relationship holds.
    assert result["matrix"]["JPY"]["EUR"] == pytest.approx(
        1 / result["matrix"]["EUR"]["JPY"]
    )


@responses.activate
def test_matrix_caches_and_degrades():
    responses.get(
        fx.FRANKFURTER_URL, body=json.dumps(SAMPLE),
        content_type="application/json",
    )
    first = fx.get_fx_matrix(currencies=["USD", "EUR"])
    second = fx.get_fx_matrix(currencies=["USD", "EUR"])  # served from cache
    assert first == second
    assert len(responses.calls) == 1


@responses.activate
def test_matrix_returns_empty_on_http_failure():
    responses.get(fx.FRANKFURTER_URL, status=500)
    assert fx.get_fx_matrix(currencies=["USD", "EUR"]) == {}
