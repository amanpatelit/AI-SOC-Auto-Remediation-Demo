# AI SOC Auto-Remediation Demo

A small, local demonstration of a guarded security-remediation workflow:

> Simulated security alert → Python triage → OPA/Rego policy decision → remediation simulation → audit log

The project is intended for learning and presentation purposes. By default, it does not change a Kubernetes cluster. A real Kubernetes change requires the explicit `--apply` flag and should only be tested in a disposable local cluster.

> **Safety note:** This is a starter demo, not a production SOC. Alert analysis is deterministic placeholder logic, not a connected LLM. IAM key revocation, cloud actions, GitHub pull requests, Slack/Teams approvals, and production integrations are not implemented. Never connect this demo to production credentials or production clusters.

## 1. What is included?

```text
ai-soc-auto-remediation-demo/
├── README.md
├── requirements.txt
├── policies/
│   └── remediation.rego             # OPA policy: allow/deny rules
├── samples/
│   ├── privileged-pod-alert.json    # Low-risk demo namespace; expected ALLOW
│   └── production-alert.json        # Protected namespace; expected DENY
├── src/
│   └── ai_soc_demo.py               # Triage, policy evaluation, guarded action, audit log
├── k8s/
│   └── sample-deployment.yaml       # Sample workload for local Kubernetes
├── tests/
│   └── test_policy.py               # Unit tests for local policy mirror
└── logs/                            # Created automatically when the demo runs
    └── audit.jsonl
```

## 2. Prerequisites

**Required for the Python-only simulation**

- Windows 10/11, macOS, or Linux
- Python 3.10 or newer
- OPA CLI for evaluating the actual Rego policy

**Required only if you want to apply the demo remediation to Kubernetes**

- Docker Desktop with its Linux engine running (Windows)
- Minikube
- kubectl

Official installation guides:

- Python: https://www.python.org/downloads/
- OPA: https://www.openpolicyagent.org/docs/latest/
- Docker Desktop: https://www.docker.com/products/docker-desktop/
- Minikube: https://minikube.sigs.k8s.io/docs/start/
- kubectl: https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/

This project uses only the Python standard library; `requirements.txt` has no third-party packages to install.

## 3. Windows 11 setup

### Step 1 — Extract the ZIP

Extract `ai-soc-auto-remediation-demo.zip`, then open PowerShell in the extracted `ai-soc-auto-remediation-demo` folder.

For example:

```powershell
cd "$HOME\Downloads\ai-soc-auto-remediation-demo"
```

Use the actual folder path where you extracted the ZIP.

### Step 2 — Verify Python

```powershell
python --version
```

You should see Python 3.10 or newer. If `python` is not recognized, install Python and enable **Add Python to PATH** during setup, then open a new PowerShell window.

### Step 3 — Install and verify OPA

Install the OPA CLI using the official OPA installation instructions. Then verify:

```powershell
opa version
```

If `opa` is not on PATH, pass its full executable path with `--opa`, for example:

```powershell
python .\src\ai_soc_demo.py --opa "C:\Tools\opa.exe"
```

Replace that example path with the actual location of your OPA executable.

### Step 4 — Optional: create a Python virtual environment

No Python packages are needed, but a virtual environment is useful for project isolation:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can skip activation; the demo uses only the Python standard library.

## 4. Run the demo (simulation mode)

### Test 1 — Development alert should be allowed

Run from the project root:

```powershell
python .\src\ai_soc_demo.py --alert .\samples\privileged-pod-alert.json
```

Expected behavior:

- The alert and triage summary are displayed.
- OPA evaluates the action against `policies/remediation.rego`.
- The `isolate_pod` action in the `aisoc-demo` development namespace should be allowed.
- The script reports `SIMULATED` and does not change Kubernetes.

### Test 2 — Production-like alert should be denied

```powershell
python .\src\ai_soc_demo.py --alert .\samples\production-alert.json
```

Expected behavior:

- The policy should return DENY for the `prod-core` namespace.
- No remediation is performed.
- The script may return exit code 1 because the policy correctly denied the action. This is expected for this test.

### Optional — Run without OPA installed

For a quick offline demonstration, use the built-in local policy mirror:

```powershell
python .\src\ai_soc_demo.py --alert .\samples\privileged-pod-alert.json --local-policy-only
python .\src\ai_soc_demo.py --alert .\samples\production-alert.json --local-policy-only
```

The local policy mirror is only a convenience for the demo; it does not invoke OPA. Use the normal command to demonstrate actual Rego evaluation.

### View the audit log

Every run writes a JSON record to:

```text
logs/audit.jsonl
```

To inspect it in PowerShell:

```powershell
Get-Content .\logs\audit.jsonl
```

## 5. Run the unit tests

From the project root:

```powershell
python -m unittest discover -s tests -v
```

The unit tests exercise the local policy mirror and do not require OPA or Kubernetes.

## 6. Optional: set up Minikube and deploy the sample workload

### Step 1 — Start Docker Desktop

Open Docker Desktop and wait until its engine is running. Verify the Docker server is available:

```powershell
docker version
docker ps
```

`docker version` should show both Client and Server sections. If it reports that `dockerDesktopLinuxEngine` cannot be found, start Docker Desktop and wait for it to finish starting before continuing. If necessary, check WSL with:

```powershell
wsl --status
wsl -l -v
```

### Step 2 — Start Minikube

Install Minikube and kubectl, then run:

```powershell
minikube start --driver=docker
minikube status
kubectl get nodes
```

The node should eventually report `Ready`.

### Step 3 — Create the demo namespace and deploy the sample

```powershell
kubectl create namespace aisoc-demo
kubectl apply -n aisoc-demo -f .\k8s\sample-deployment.yaml
kubectl get pods -n aisoc-demo
```

Wait for the pod to reach `Running`. The sample manifest uses a restricted container security context; it is a sample workload, not itself a deliberately privileged pod.

### Step 4 — Simulate the remediation first

```powershell
python .\src\ai_soc_demo.py --alert .\samples\privileged-pod-alert.json --namespace aisoc-demo
```

This is still simulation mode. No Kubernetes resource is changed.

### Step 5 — Apply the demo quarantine NetworkPolicy (optional)

Only do this in a disposable local cluster and test namespace after reviewing the code:

```powershell
python .\src\ai_soc_demo.py --alert .\samples\privileged-pod-alert.json --namespace aisoc-demo --apply
```

If the policy allows the action, the script applies a NetworkPolicy named `aisoc-quarantine-demo`. It selects pods labelled `app: aisoc-demo` and denies ingress and egress for those selected pods.

**Important:**

- The NetworkPolicy is namespace-scoped and selects all pods with the `app: aisoc-demo` label in that namespace.
- NetworkPolicy enforcement depends on the cluster's network plugin.
- This action is a demo quarantine control; it does not actually detect or isolate a specific pod by its name.
- Do not run this in a shared or production cluster.
- The code blocks known production namespaces, but this safeguard is not a substitute for Kubernetes RBAC, admission controls, or human review.

To remove the demo policy:

```powershell
kubectl delete networkpolicy aisoc-quarantine-demo -n aisoc-demo
```

To remove the sample deployment and namespace when finished:

```powershell
kubectl delete namespace aisoc-demo
```

## 7. How the policy works

The Rego policy in `policies/remediation.rego` defaults to deny. It allows only the `isolate_pod` demo action when:

- Confidence is at least 0.95
- A namespace is provided
- The namespace is not on the protected namespace list
- The environment is not production

The policy is intentionally small and explicit. It is not a complete security policy for a real platform.

## 8. Troubleshooting

| Symptom | What to check |
| --- | --- |
| `python` is not recognized | Install Python and enable PATH, then reopen PowerShell. |
| `opa` is not recognized | Install OPA or pass the full path with `--opa`. |
| OPA evaluation errors | Run `opa version` and check the syntax in `policies/remediation.rego`. The demo fails closed if OPA errors. |
| Docker says `dockerDesktopLinuxEngine` cannot be found | Start Docker Desktop and wait for the Linux engine to be ready. Check `wsl --status` and `wsl -l -v`. |
| Minikube fails to start | Check `docker ps`, then run `minikube logs`. |
| Pod is not `Running` | Run `kubectl describe pod -n aisoc-demo` and `kubectl get events -n aisoc-demo`. |
| NetworkPolicy has no effect | Check whether the Minikube network plugin supports NetworkPolicy enforcement. |

## 9. Suggested live-demo script

1. Run `privileged-pod-alert.json` and show the policy decision ALLOW.
2. Explain that the default mode is simulation and no cluster changes occur.
3. Run `production-alert.json` and show the policy decision DENY.
4. Open `logs/audit.jsonl` to show the recorded outcomes.
5. If time permits, use a disposable Minikube cluster to apply and then remove the demo NetworkPolicy.
<<<<<<< HEAD

> **Key message:** AI-style triage proposes a remediation; deterministic policy decides whether it may proceed. This demo's triage is currently rule-based placeholder logic, so a real LLM can be integrated as a later extension.
=======
Key message: AI-style triage proposes a remediation; deterministic policy decides whether it may proceed. This demo's triage is currently rule-based placeholder logic, so a real LLM can be integrated as a later extension.
>>>>>>> 9309f285c4c4d7f9c84a794e97c482c4d060a9bd
