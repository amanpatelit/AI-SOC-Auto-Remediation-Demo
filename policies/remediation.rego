package aisoc.remediation

import rego.v1

default allow := false

# Only this low-impact demo action is executable by this project.
allowed_actions := {"isolate_pod"}

production_namespaces := {
  "prod",
  "production",
  "prod-core",
  "kube-system",
  "kube-public",
  "kube-node-lease",
}

allow if {
  input.action in allowed_actions
  input.confidence >= 0.95
  input.namespace != ""
  not input.namespace in production_namespaces
  input.environment != "production"
}
