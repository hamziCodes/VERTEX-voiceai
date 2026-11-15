"""Phase 14: bounded-cardinality metrics with real histograms."""

from __future__ import annotations

import re

import pytest

from core.observability.metrics import (
    OVERFLOW_LABEL_VALUE,
    MetricsRegistry,
    get_metrics_registry,
)


def test_counter_with_labels_exports_each_series() -> None:
    reg = MetricsRegistry()
    c = reg.counter("jobs_total", "Jobs", labelnames=("job", "outcome"))
    c.labels(job="post_call", outcome="succeeded").inc()
    c.labels(job="post_call", outcome="succeeded").inc(2)
    c.labels(job="post_call", outcome="failed").inc()

    text = reg.export_prometheus_text()
    assert "# TYPE jobs_total counter" in text
    assert 'jobs_total{job="post_call",outcome="succeeded"} 3.0' in text
    assert 'jobs_total{job="post_call",outcome="failed"} 1.0' in text


def test_histogram_exports_cumulative_buckets_sum_and_count() -> None:
    reg = MetricsRegistry()
    h = reg.histogram("lat_ms", "Latency", buckets=(100.0, 500.0, 1000.0))
    for value in (50.0, 120.0, 480.0, 900.0, 4000.0):
        h.observe(value)

    text = reg.export_prometheus_text()
    assert 'lat_ms_bucket{le="100.0"} 1' in text
    assert 'lat_ms_bucket{le="500.0"} 3' in text
    assert 'lat_ms_bucket{le="1000.0"} 4' in text
    assert 'lat_ms_bucket{le="+Inf"} 5' in text
    assert "lat_ms_count 5" in text
    assert "lat_ms_sum 5550.0" in text
    assert h.count == 5
    assert h.sum == 5550.0


def test_histogram_percentiles_interpolate_within_buckets() -> None:
    reg = MetricsRegistry()
    h = reg.histogram("p_ms", "P", buckets=(100.0, 200.0, 400.0, 800.0))
    for _ in range(50):
        h.observe(90.0)
    for _ in range(45):
        h.observe(150.0)
    for _ in range(5):
        h.observe(700.0)

    p50 = h.quantile(0.50)
    p95 = h.quantile(0.95)
    p99 = h.quantile(0.99)
    assert p50 is not None and 0.0 < p50 <= 100.0
    assert p95 is not None and 100.0 < p95 <= 200.0
    assert p99 is not None and 400.0 < p99 <= 800.0
    assert reg.histogram("empty_ms", "E").quantile(0.5) is None


def test_unbounded_or_identifying_label_names_are_rejected() -> None:
    reg = MetricsRegistry()
    for name in (
        "tenant_id",
        "session_id",
        "call_id",
        "phone",
        "email",
        "user_id",
        "turn_id",
    ):
        with pytest.raises(ValueError):
            reg.counter(f"bad_{name}", "x", labelnames=(name,))


def test_series_cardinality_is_capped_and_overflow_is_counted() -> None:
    reg = MetricsRegistry(max_series_per_metric=3)
    c = reg.counter("routes_total", "Routes", labelnames=("route",))
    for i in range(10):
        c.labels(route=f"/r{i}").inc()

    text = reg.export_prometheus_text()
    series = [line for line in text.splitlines() if line.startswith("routes_total{")]
    assert len(series) == 4  # three real series plus one overflow bucket
    assert f'routes_total{{route="{OVERFLOW_LABEL_VALUE}"}} 7.0' in text
    assert 'ucve_metrics_series_overflow_total{metric="routes_total"} 7.0' in text


def test_label_values_are_escaped_and_truncated() -> None:
    reg = MetricsRegistry()
    c = reg.counter("esc_total", "Esc", labelnames=("route",))
    c.labels(route='a"b\\c\nd').inc()
    text = reg.export_prometheus_text()
    assert 'esc_total{route="a\\"b\\\\c\\nd"} 1.0' in text
    c.labels(route="x" * 500).inc()
    long_line = [
        line for line in reg.export_prometheus_text().splitlines() if "xxxx" in line
    ][0]
    assert len(long_line) < 200


def test_wrong_label_set_is_an_error() -> None:
    reg = MetricsRegistry()
    c = reg.counter("lbl_total", "L", labelnames=("job",))
    with pytest.raises(ValueError):
        c.labels(other="x")
    with pytest.raises(ValueError):
        c.inc()  # labelled metric requires labels


def test_gauge_set_inc_dec() -> None:
    reg = MetricsRegistry()
    g = reg.gauge("active", "Active", labelnames=("service",))
    g.labels(service="worker-raw").inc()
    g.labels(service="worker-raw").inc()
    g.labels(service="worker-raw").dec()
    g.labels(service="control-plane").set(4)
    text = reg.export_prometheus_text()
    assert "# TYPE active gauge" in text
    assert 'active{service="worker-raw"} 1.0' in text
    assert 'active{service="control-plane"} 4.0' in text


def test_registering_same_name_with_different_type_fails() -> None:
    reg = MetricsRegistry()
    reg.counter("dup", "d")
    with pytest.raises(ValueError):
        reg.histogram("dup", "d")


def test_export_is_parseable_prometheus_exposition() -> None:
    """Every sample line matches the exposition grammar."""
    text = get_metrics_registry().export_prometheus_text()
    sample = re.compile(
        r'^[a-zA-Z_:][a-zA-Z0-9_:]*(\{([a-zA-Z_][a-zA-Z0-9_]*="([^"\\\n]|\\.)*",?)*\})? '  # noqa: E501
        r"[-+]?([0-9.]+([eE][-+]?[0-9]+)?|Inf|NaN)$"
    )
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        assert sample.match(line), line


def test_standard_metrics_are_registered() -> None:
    names = set(get_metrics_registry().names())
    for required in (
        "ucve_turn_latency_ms",
        "ucve_turn_stage_ms",
        "ucve_barge_in_total",
        "ucve_provider_failover_total",
        "ucve_buffer_drop_total",
        "ucve_active_sessions",
        "ucve_http_requests_total",
        "ucve_http_request_duration_ms",
        "ucve_event_loop_lag_ms",
        "ucve_jobs_total",
        "ucve_job_queue_depth",
        "ucve_alerts_total",
    ):
        assert required in names, required
