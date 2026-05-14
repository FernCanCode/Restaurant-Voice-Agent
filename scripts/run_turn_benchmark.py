#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
from pathlib import Path

import httpx


TARGET_HOST = os.environ.get("TARGET_HOST", "http://localhost:8000").rstrip("/")
TARGET_ENDPOINT = "POST /api/turn"
TOTAL_REQUESTS = int(os.environ.get("BENCHMARK_TOTAL_REQUESTS", "240"))
CONCURRENCY = int(os.environ.get("BENCHMARK_CONCURRENCY", "40"))
THRESHOLD_RPS = int(os.environ.get("BENCHMARK_MIN_RPS", "10"))
THRESHOLD_FAIL = float(os.environ.get("BENCHMARK_MAX_FAILURE_RATE", "0.05"))
REQUEST_TIMEOUT = float(os.environ.get("BENCHMARK_TIMEOUT_SECONDS", "10"))
UTTERANCE = os.environ.get("BENCHMARK_UTTERANCE", "What tacos do you have?")


async def _create_session(client: httpx.AsyncClient) -> str:
    response = await client.post(
        f"{TARGET_HOST}/api/sessions",
        json={"channel": "browser"},
    )
    response.raise_for_status()
    return response.json()["session_id"]


async def _run_turn(
    client: httpx.AsyncClient, session_id: str, semaphore: asyncio.Semaphore
) -> tuple[bool, float]:
    async with semaphore:
        start = time.perf_counter()
        try:
            response = await client.post(
                f"{TARGET_HOST}/api/turn",
                json={
                    "session_id": session_id,
                    "utterance": UTTERANCE,
                    "channel": "browser",
                    "metadata": {},
                },
            )
            response.raise_for_status()
            success = True
        except Exception:
            success = False
        latency_ms = (time.perf_counter() - start) * 1000.0
        return success, latency_ms


def _percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(percent * (len(ordered) - 1))))
    return ordered[index]


def _write_report(report: dict[str, object]) -> None:
    report_path = Path("reports/benchmarks.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


async def main() -> None:
    limits = httpx.Limits(max_connections=CONCURRENCY * 2, max_keepalive_connections=CONCURRENCY)
    timeout = httpx.Timeout(REQUEST_TIMEOUT)
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        health = await client.get(f"{TARGET_HOST}/health")
        health.raise_for_status()

        session_ids = await asyncio.gather(
            *[_create_session(client) for _ in range(TOTAL_REQUESTS)]
        )

        semaphore = asyncio.Semaphore(CONCURRENCY)
        started_at = time.perf_counter()
        outcomes = await asyncio.gather(
            *[_run_turn(client, session_id, semaphore) for session_id in session_ids]
        )
        duration_seconds = max(time.perf_counter() - started_at, 0.001)

    latencies = [latency for _, latency in outcomes]
    failed_requests = sum(1 for success, _ in outcomes if not success)
    total_requests = len(outcomes)
    failure_rate = failed_requests / total_requests if total_requests else 0.0
    requests_per_second = (total_requests - failed_requests) / duration_seconds

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target_host": TARGET_HOST,
        "target_endpoint": TARGET_ENDPOINT,
        "duration_seconds": round(duration_seconds, 3),
        "total_requests": total_requests,
        "failed_requests": failed_requests,
        "requests_per_second": round(requests_per_second, 3),
        "failure_rate": round(failure_rate, 4),
        "median_latency_ms": round(statistics.median(latencies), 3) if latencies else 0.0,
        "p95_latency_ms": round(_percentile(latencies, 0.95), 3),
        "p99_latency_ms": round(_percentile(latencies, 0.99), 3),
        "thresholds": {
            "min_requests_per_second": THRESHOLD_RPS,
            "max_failure_rate": THRESHOLD_FAIL,
        },
        "passed": requests_per_second >= THRESHOLD_RPS and failure_rate <= THRESHOLD_FAIL,
        "notes": (
            "Concurrent benchmark against the running Docker app using one browser "
            "session per request on POST /api/turn."
        ),
    }
    _write_report(report)


if __name__ == "__main__":
    asyncio.run(main())
