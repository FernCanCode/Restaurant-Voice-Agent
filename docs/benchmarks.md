# Benchmark and Load Test Documentation

## Overview

The benchmark verifies whether the live application can handle repeated agent-turn requests under local grading conditions.

The load test is not intended to prove production call-center scale. It is intended to satisfy the project’s stress/robustness requirement and demonstrate that the app can handle concurrent local requests without crashing.

## Benchmark Scope

- target system: FastAPI backend
- target workflow: representative restaurant voice-agent turns
- target endpoint: `POST /api/turn`
- uses the same backend path as browser and phone mode after speech transcription
- does not require a real Twilio phone call
- does not require a real browser microphone
- does not require payment processing
- does not require live restaurant website scraping

## Load Test Tool

```text
Tool: Locust
File: tests/load/locustfile.py
Command: make loadtest
Raw report: reports/benchmarks.json
```

## Target Endpoint

```text
POST /api/turn
```

`/api/turn` is the headline endpoint because browser voice, Twilio transcription handling, and automated tests all route caller utterances through the same shared agent orchestrator or equivalent internal service.

## Test Scenario

The Locust scenario simulates representative short caller turns, such as:
- starting or using a session
- asking a menu question
- adding an item
- asking for total
- requesting readback

The load test should use deterministic or mocked LLM behavior where appropriate so load results are not dominated by external API latency, rate limits, or API cost.

The test does not require real Twilio calls or browser microphone access.

## Performance Targets

Target thresholds from `grading/manifest.yaml`:
```text
Minimum request rate: 10 requests per second
Maximum error rate: 5 percent
Full test duration: 60 seconds
```

Useful latency fields to report:
- median latency
- p95 latency
- p99 latency
- total requests
- failed requests
- failure rate

## Running the Load Test

```bash
make loadtest
```

Expected behavior:
- starts or targets the local running app
- runs Locust against the configured local endpoint
- writes results to `reports/benchmarks.json`
- prints a short summary

If the app must be running first:
```bash
docker compose up --build
make loadtest
```

## Output Artifacts

| Artifact | Path | Purpose |
|---|---|---|
| Raw benchmark report | `reports/benchmarks.json` | Machine-readable load-test results |
| Benchmark documentation | `docs/benchmarks.md` | Methodology, targets, and interpretation |
| Locust scenario | `tests/load/locustfile.py` | Load-test implementation |

## Result Fields

`reports/benchmarks.json` should include:
- timestamp
- target host
- target endpoint
- duration seconds
- total requests
- failed requests
- requests per second
- failure rate
- median latency ms
- p95 latency ms
- p99 latency ms
- notes
- pass/fail status against thresholds

Example placeholder structure:
```json
{
  "timestamp": "TO_BE_FILLED_AFTER_LOADTEST",
  "target_host": "http://localhost:8000",
  "target_endpoint": "POST /api/turn",
  "duration_seconds": 60,
  "total_requests": 0,
  "failed_requests": 0,
  "requests_per_second": 0.0,
  "failure_rate": 0.0,
  "median_latency_ms": 0.0,
  "p95_latency_ms": 0.0,
  "p99_latency_ms": 0.0,
  "thresholds": {
    "min_requests_per_second": 10,
    "max_failure_rate": 0.05
  },
  "passed": false,
  "notes": "TO_BE_FILLED_AFTER_LOADTEST"
}
```

## Interpreting Results

- Passing means the app met or exceeded 10 requests per second and stayed under 5 percent error rate during the configured run.
- Failing does not necessarily mean the voice agent is functionally wrong, but it indicates stress/robustness needs improvement or the test environment was resource constrained.
- External LLM latency and rate limits can distort load testing, so tests should use mocked or deterministic LLM behavior where appropriate.
- The goal is stable local service behavior, not production-scale call-center certification.

## Current Results

Final measured results will be filled after `make loadtest` is implemented and run.

| Metric | Target | Measured |
|---|---:|---:|
| Requests per second | >= 10 | TBD |
| Failure rate | < 5% | TBD |
| Median latency | Report only | TBD |
| p95 latency | Report only | TBD |
| p99 latency | Report only | TBD |

## Limitations

- benchmark is local and environment-dependent
- benchmark does not represent production Twilio call capacity
- benchmark does not include real phone network latency
- benchmark does not include browser speech recognition latency
- benchmark may mock external LLM calls to avoid rate limits/costs
- benchmark focuses on backend turn handling

## Benchmark Success Criteria

- `tests/load/locustfile.py` exists
- `make loadtest` runs
- `reports/benchmarks.json` is generated
- target endpoint is `POST /api/turn`
- result fields are documented
- benchmark target is at least 10 requests per second
- benchmark maximum error rate is under 5 percent
- measured results are not invented before execution
