"""Versioned lab policy plus an opt-in local DCGM runner; no remote commands."""

import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Literal

from pydantic import Field

from .contracts import Strict


class Check(Strict):
    name: str
    result: Literal["pass", "fail", "skip", "unknown"]


class DiagnosticEvidence(Strict):
    schema_version: Literal["1.0"] = "1.0"
    origin: Literal["synthetic", "replayed", "live"]
    hardware_id: str
    driver_version: str
    dcgm_version: str
    captured_at: str
    duration_seconds: float = Field(ge=0)
    coverage_ratio: float = Field(ge=0, le=1)
    checks: list[Check] = Field(max_length=100)
    raw_sha256: str | None = None
    source: str


class ReadinessPolicy(Strict):
    name: str = "fleetops-lab-readiness-v1"
    minimum_duration_seconds: float = Field(default=120, gt=0)
    minimum_coverage_ratio: float = Field(default=0.95, gt=0, le=1)
    required_checks: list[str] = Field(
        default_factory=lambda: ["software", "memory", "targeted_stress"]
    )


def assess(evidence: DiagnosticEvidence, policy: ReadinessPolicy | None = None) -> dict:
    policy = policy or ReadinessPolicy()
    checks = {c.name: c.result for c in evidence.checks}
    failures = [c.name for c in evidence.checks if c.result == "fail"]
    gaps = [name for name in policy.required_checks if checks.get(name) != "pass"]
    reasons = []
    if failures:
        reasons.append("Failed diagnostics: " + ", ".join(failures))
    if evidence.duration_seconds < policy.minimum_duration_seconds:
        reasons.append("Observation duration below policy minimum")
    if evidence.coverage_ratio < policy.minimum_coverage_ratio:
        reasons.append("Telemetry/diagnostic coverage below policy minimum")
    if gaps:
        reasons.append("Required checks absent, skipped or unsuccessful: " + ", ".join(gaps))
    if not evidence.hardware_id or not evidence.driver_version or not evidence.dcgm_version:
        reasons.append("Missing hardware/software identity")
    if len(checks) != len(evidence.checks):
        reasons.append("Duplicate check identities require operator review")
    status = "fail" if failures else "insufficient_data" if reasons else "pass"
    return dict(
        status=status,
        policy=policy.model_dump(),
        evidence=evidence.model_dump(),
        reasons=reasons,
        physical_gpu_validated=status == "pass" and evidence.origin == "live",
        scope="Lab readiness only; a finite test establishes no long-term MTBI or NVIDIA certification",
    )


def sample_evidence(case: str = "pass") -> DiagnosticEvidence:
    if case not in {"pass", "fail", "incomplete"}:
        raise ValueError("Unknown readiness example")
    return DiagnosticEvidence(
        origin="synthetic",
        hardware_id="LAB-GPU-0000",
        driver_version="illustrative-driver",
        dcgm_version="illustrative-dcgm",
        captured_at="2026-10-01T00:00:00Z",
        duration_seconds=180 if case != "incomplete" else 20,
        coverage_ratio=0.99 if case != "incomplete" else 0.5,
        checks=[
            Check(name=name, result="fail" if case == "fail" and name == "memory" else "pass")
            for name in ("software", "memory", "targeted_stress")
        ],
        source="Authored policy fixture; no physical GPU execution",
    )


def parse_dcgm(document: dict) -> list[Check]:
    """Strict legacy test_categories contract; unknown release shapes stay unknown."""
    root = document.get("DCGM GPU Diagnostic", {})
    if root.get("runtime_error") or document.get("runtime_error"):
        return [Check(name="runtime", result="fail")]
    checks = []
    aliases = {
        "software": "software",
        "deployment": "software",
        "memory": "memory",
        "gpu memory": "memory",
        "targeted stress": "targeted_stress",
        "targeted_stress": "targeted_stress",
    }
    for category in root.get("test_categories", []):
        category_checks = []
        for test in category.get("tests", []):
            name = aliases.get(str(test.get("name", "")).lower(), str(test.get("name", "unknown")))
            statuses = [str(r.get("status", "unknown")).lower() for r in test.get("results", [])]
            result = (
                "fail"
                if "fail" in statuses
                else "pass"
                if statuses and all(s == "pass" for s in statuses)
                else "skip"
                if statuses and all(s == "skip" for s in statuses)
                else "unknown"
            )
            checks.append(Check(name=name, result=result))
            category_checks.append(result)
        if (
            str(category.get("category", "")).lower() in {"deployment", "software"}
            and category_checks
        ):
            if not any(c.name == "software" for c in checks):
                result = (
                    "fail"
                    if "fail" in category_checks
                    else "pass"
                    if all(s == "pass" for s in category_checks)
                    else "unknown"
                )
                checks.append(Check(name="software", result=result))
    return checks


def run_local(
    output_dir: Path,
    *,
    execute: bool = False,
    idle_confirmed: bool = False,
    gpu: int = 0,
    timeout: int = 900,
) -> dict:
    if not execute or not idle_confirmed:
        raise ValueError(
            "Live diagnostics require --execute and --idle-confirmed on an idle, supported GPU"
        )
    if gpu < 0 or gpu > 1024 or not 1 <= timeout <= 3600:
        raise ValueError("Invalid GPU or timeout")
    output_dir.mkdir(parents=True, exist_ok=True)
    binary = shutil.which("dcgmi")
    if not binary:
        result = dict(
            status="unavailable",
            origin="live_attempt",
            reason="dcgmi is not installed; no physical test ran",
        )
        (output_dir / "live-attempt.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    command = [binary, "diag", "--run", "3", "--entity-id", f"gpu:{gpu}", "--json"]
    started = monotonic()
    try:
        process = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
        stdout, stderr, code = process.stdout, process.stderr, process.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout or ""
        stderr, code = "Diagnostic timed out; operator must verify hardware state", -1
    duration = monotonic() - started
    (output_dir / "dcgm-stdout.json").write_text(stdout)
    (output_dir / "dcgm-stderr.txt").write_text(stderr)
    try:
        document = json.loads(stdout)
        checks = parse_dcgm(document)
    except (ValueError, TypeError, AttributeError):
        checks = []
    if code:
        checks.append(Check(name="process_exit", result="fail"))
    hardware_id, driver_version, dcgm_version = "", "", ""
    try:
        identity = subprocess.run(
            [
                "nvidia-smi",
                f"--id={gpu}",
                "--query-gpu=uuid,driver_version",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if identity.returncode == 0:
            hardware_id, driver_version = [x.strip() for x in identity.stdout.strip().split(",", 1)]
        version = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=15, check=False
        )
        if version.returncode == 0:
            dcgm_version = version.stdout.strip()[:300]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    required = ReadinessPolicy().required_checks
    coverage = sum(
        any(c.name == name and c.result in {"pass", "fail"} for c in checks) for name in required
    ) / len(required)
    evidence = DiagnosticEvidence(
        origin="live",
        hardware_id=hardware_id,
        driver_version=driver_version,
        dcgm_version=dcgm_version,
        captured_at=datetime.now(UTC).isoformat(),
        duration_seconds=duration,
        coverage_ratio=coverage,
        checks=checks,
        raw_sha256=hashlib.sha256(stdout.encode()).hexdigest(),
        source="Local dcgmi subprocess; raw files retained alongside report",
    )
    report = assess(evidence)
    report["command"] = command
    (output_dir / "readiness.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
