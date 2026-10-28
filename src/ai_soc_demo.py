#!/usr/bin/env python3
"""Safety-first AI SOC auto-remediation demo. Standard library only."""

from __future__ import annotations
import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_NAMESPACES = {
    "prod", "production", "prod-core", "kube-system",
    "kube-public", "kube-node-lease",
}


def local_policy_decision(policy_input: dict) -> bool:
    """Fail-closed local mirror used for tests and when OPA is unavailable."""
    try:
        return (
            policy_input.get("action") == "isolate_pod"
            and float(policy_input.get("confidence", 0)) >= 0.95
            and bool(policy_input.get("namespace"))
            and policy_input.get("namespace") not in PRODUCTION_NAMESPACES
            and policy_input.get("environment") != "production"
        )
    except (TypeError, ValueError):
        return False


def opa_policy_decision(policy_input: dict, opa_path: str) -> bool:
    """Evaluate the Rego policy using the OPA CLI; fail closed on errors."""
    opa = shutil.which(opa_path) if not Path(opa_path).exists() else opa_path
    if not opa:
        raise FileNotFoundError(
            "OPA CLI not found. Install OPA or pass --opa PATH. "
            "This demo requires OPA for end-to-end policy evaluation."
        )
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as f:
        json.dump(policy_input, f)
        input_path = f.name
    try:
        cmd = [
            opa, "eval", "--format", "raw",
            "--data", str(ROOT / "policies" / "remediation.rego"),
            "--input", input_path,
            "data.aisoc.remediation.allow",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            raise RuntimeError(f"OPA evaluation failed: {result.stderr.strip()}")
        return result.stdout.strip().lower() == "true"
    finally:
        Path(input_path).unlink(missing_ok=True)


def triage(alert: dict) -> dict:
    """Deterministic demo triage; this is a placeholder for a real AI agent."""
    confidence = float(alert.get("confidence", 0))
    severity = str(alert.get("severity", "unknown")).lower()
    alert_type = str(alert.get("type", "unknown"))
    action = str(alert.get("proposed_action", ""))
    summary = (
        f"{severity.upper()} alert '{alert_type}' for pod "
        f"'{alert.get('pod', 'unknown')}' in namespace "
        f"'{alert.get('namespace', 'unknown')}'."
    )
    return {
        "summary": summary,
        "confidence": confidence,
        "risk": "high" if severity in {"high", "critical"} else "medium",
        "action": action,
    }


def write_audit(record: dict) -> None:
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    with (log_dir / "audit.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def apply_kubernetes_remediation(namespace: str, kubectl: str = "kubectl") -> None:
    """Apply a restrictive demo NetworkPolicy; no shell interpolation."""
    if namespace in PRODUCTION_NAMESPACES:
        raise RuntimeError(f"Refusing to change protected namespace: {namespace}")
    exe = shutil.which(kubectl) if not Path(kubectl).exists() else kubectl
    if not exe:
        raise FileNotFoundError("kubectl not found. Install it or pass --kubectl PATH.")
    manifest = f"""apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: aisoc-quarantine-demo
  namespace: {namespace}
spec:
  podSelector:
    matchLabels:
      app: aisoc-demo
  policyTypes:
    - Ingress
    - Egress
  ingress: []
  egress: []
"""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8", delete=False) as f:
        f.write(manifest)
        manifest_path = f.name
    try:
        result = subprocess.run(
            [exe, "apply", "-f", manifest_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "kubectl apply failed")
        print(result.stdout.strip())
    finally:
        Path(manifest_path).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local AI SOC remediation demo")
    parser.add_argument("--alert", default=str(ROOT / "samples" / "privileged-pod-alert.json"))
    parser.add_argument("--namespace", help="Override alert namespace for a local test namespace")
    parser.add_argument("--opa", default="opa", help="OPA CLI executable or full path")
    parser.add_argument("--kubectl", default="kubectl", help="kubectl executable or full path")
    parser.add_argument("--apply", action="store_true", help="Apply approved demo NetworkPolicy; otherwise simulate only")
    parser.add_argument("--local-policy-only", action="store_true",
                        help="Use built-in policy mirror if OPA is not installed (for quick offline demonstration)")
    args = parser.parse_args()

    alert_path = Path(args.alert)
    if not alert_path.is_absolute():
        alert_path = (Path.cwd() / alert_path).resolve()
    try:
        alert = json.loads(alert_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ERROR] Could not read alert JSON: {exc}", file=sys.stderr)
        return 2

    namespace = args.namespace or alert.get("namespace", "")
    analysis = triage(alert)
    policy_input = {
        "action": analysis["action"],
        "confidence": analysis["confidence"],
        "namespace": namespace,
        "environment": alert.get("environment", "unknown"),
    }

    print("=== AI SOC AUTO-REMEDIATION DEMO ===")
    print(f"[ALERT] {alert.get('alert_id', 'unknown')} | {analysis['summary']}")
    print(f"[AI]    Risk={analysis['risk']} | Confidence={analysis['confidence']:.2f}")
    print(f"[PLAN]  Proposed action: {analysis['action']}")

    try:
        if args.local_policy_only:
            allowed = local_policy_decision(policy_input)
            policy_source = "local policy mirror (OPA not invoked)"
        else:
            allowed = opa_policy_decision(policy_input, args.opa)
            policy_source = "OPA Rego policy"
    except Exception as exc:
        print(f"[OPA]   ERROR / FAIL-CLOSED: {exc}", file=sys.stderr)
        record = {
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "alert_id": alert.get("alert_id"),
            "namespace": namespace,
            "action": analysis["action"],
            "decision": "ERROR_DENY",
            "reason": str(exc),
        }
        write_audit(record)
        return 3

    print(f"[OPA]   Decision: {'ALLOW' if allowed else 'DENY'} ({policy_source})")
    result = "DENIED"
    reason = "Policy denied action"
    if allowed:
        if args.apply:
            try:
                apply_kubernetes_remediation(namespace, args.kubectl)
                result = "APPLIED"
                reason = "Demo NetworkPolicy applied"
                print("[FIX]   Remediation applied.")
            except Exception as exc:
                result = "APPLY_FAILED"
                reason = str(exc)
                print(f"[FIX]   Apply failed: {exc}", file=sys.stderr)
        else:
            result = "SIMULATED"
            reason = "No cluster changes made; rerun with --apply to apply in a test namespace"
            print("[FIX]   Simulation only; no Kubernetes changes made.")
    else:
        print("[FIX]   Blocked. No changes made.")

    record = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "alert_id": alert.get("alert_id"),
        "namespace": namespace,
        "action": analysis["action"],
        "policy_decision": "ALLOW" if allowed else "DENY",
        "result": result,
        "reason": reason,
    }
    write_audit(record)
    print(f"[AUDIT] Result={result} | Log: logs/audit.jsonl")
    return 0 if allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
