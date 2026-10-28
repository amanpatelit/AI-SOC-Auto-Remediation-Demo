# AI SOC Auto-Remediation Demo image
# Runs the Python simulation with the OPA CLI available for real Rego evaluation.
FROM python:3.12-slim

# --- OPA CLI -----------------------------------------------------------------
# Pinned OPA version; static linux/amd64 binary from the official release.
ARG OPA_VERSION=0.70.0
ARG TARGETARCH=amd64
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl; \
    curl -fsSL -o /usr/local/bin/opa \
        "https://github.com/open-policy-agent/opa/releases/download/v${OPA_VERSION}/opa_linux_${TARGETARCH}_static"; \
    chmod +x /usr/local/bin/opa; \
    opa version; \
    apt-get purge -y curl; \
    apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/*

# --- Application -------------------------------------------------------------
WORKDIR /app
COPY src/ ./src/
COPY policies/ ./policies/
COPY samples/ ./samples/

# Audit log directory (also mountable as a volume).
RUN mkdir -p /app/logs

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Default: simulation mode against the bundled development alert.
# OPA evaluates policies/remediation.rego; no cluster changes are made.
ENTRYPOINT ["python", "/app/src/ai_soc_demo.py"]
CMD ["--alert", "/app/samples/privileged-pod-alert.json"]
