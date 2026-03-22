# k8s-observability-mcp

An MCP server for Kubernetes observability and diagnostics.

This project exposes LLM-friendly tools for inspecting a Kubernetes cluster through:

- Kubernetes API
- Prometheus
- Jaeger
- Neo4j
- controlled shell execution

It is designed so an MCP client or agent can query cluster topology, logs, metrics, traces, and service dependencies through a single server.

---

## Features

### Topology
- Cluster overview of pods and services
- Resolve service -> pods
- Resolve pod -> services
- Service dependency queries from Neo4j
- Service neighborhood map from Neo4j
- Combined runtime + graph topology summary

### Metrics
- Pod metrics from Prometheus
- Service metrics aggregated from pod metrics
- Pod time-range metrics
- Service time-range metrics
- Pod triage metrics
- Service triage metrics

### Logs
- Read pod logs
- Read service logs across all selected pods
- Important-line filtering
- Pod log summaries
- Service log summaries

### Traces
- Trace summaries from Jaeger
- Trace details by trace ID
- Error-focused trace inspection

### Shell
- Restricted shell execution
- Restricted kubectl execution
- Safe command policy inspection

---

## Project structure

```text
k8s-observability-mcp/
├── app/
│   ├── config.py
│   ├── dependencies.py
│   └── server.py
│
├── clients/
│   ├── base_k8s_client.py
│   ├── jaeger_client.py
│   ├── neo4j_client.py
│   ├── prometheus_client.py
│   └── shell_client.py
│
├── services/
│   ├── logs_service.py
│   ├── metrics_service.py
│   ├── shell_service.py
│   ├── topology_service.py
│   └── trace_service.py
│
├── tools/
│   ├── __init__.py
│   ├── logs.py
│   ├── metrics.py
│   ├── shell.py
│   ├── topology.py
│   └── traces.py
│
├── .env.example
├── main.py
├── pyproject.toml
└── README.md