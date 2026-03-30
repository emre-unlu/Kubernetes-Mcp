# Kubernetes-Mcp

An MCP server for Kubernetes observability and diagnostics.

This project exposes LLM-friendly tools for inspecting a Kubernetes cluster through:

- Kubernetes API
- Prometheus
- Jaeger
- Neo4j
- controlled shell execution

It is designed so an MCP client or agent can query cluster topology, logs, metrics, traces, and service dependencies through a single server.

---


## How to run

### 1. Install dependencies

From the project root:
```
poetry install
```
### 2. Create your environment file

Copy the template:
```
cp .env.example .env
```
On Windows PowerShell:
```
Copy-Item .env.example .env
```
Then fill in the values you need in .env, for example:
```
K8S_NAMESPACE=default
PROMETHEUS_URL=http://localhost:9090
JAEGER_URL=http://localhost:16686
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=yourpassword
NEO4J_DATABASE=neo4j
```
### 3. Start the MCP server
```
poetry run python main.py
```
If you added the Poetry script entry, you can also run:
```
poetry run kubernetes-mcp
```
### 4. Run the smoke test
```
poetry run python -m tests.smoke_test
```
This checks:
- backend availability
- Kubernetes topology
- logs
- metrics
- shell execution
- optional trace and graph integration

### 5. Optional local backends

Start Jaeger locally:
```
docker run --rm --name jaeger \
  -e COLLECTOR_OTLP_ENABLED=true \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest
```
Start Neo4j locally:
```
docker run --rm --name neo4j \
  -p 7474:7474 \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/testpassword123 \
  neo4j:latest
```
Then set in .env:
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=testpassword123
NEO4J_DATABASE=neo4j
```
Prometheus must be reachable at the URL configured in .env, for example:
```
PROMETHEUS_URL=http://localhost:9090
```
If Prometheus is running inside your cluster, you can expose it with kubectl port-forward.


# Available Tools

This document lists the tools currently exposed by the `Kubernetes-Mcp` server, grouped by capability.

## Backend / system health

- `get_backend_status`  
  Returns availability and configuration status for Kubernetes, Prometheus, Jaeger, and Neo4j.

## Kubernetes topology / cluster structure

- `get_cluster_overview(namespace: str | None = None)`  
  Returns a namespace overview of pods and services.

- `get_pods_from_service(service_name: str, namespace: str | None = None)`  
  Returns the pods selected by a Kubernetes Service.

- `get_services_from_pod(pod_name: str, namespace: str | None = None)`  
  Returns the Services that select a given Pod.

## Neo4j dependency / topology graph

- `get_service_dependencies(service_name: str)`  
  Returns direct service dependencies from Neo4j.

- `get_services_used_by(service_name: str)`  
  Returns services that depend on the given service.

- `get_service_map(service_name: str, depth: int = 2)`  
  Returns a bounded dependency neighborhood around a service.

- `get_service_topology_summary(service_name: str, namespace: str | None = None, depth: int = 2)`  
  Returns a combined runtime + graph topology summary for a service.

## Logs

- `get_pod_logs(pod_name: str, namespace: str | None = None, tail_lines: int = 200, important_only: bool = True)`  
  Returns pod logs.

- `get_service_logs(service_name: str, namespace: str | None = None, tail_lines_per_pod: int = 200, important_only: bool = True)`  
  Returns logs for all pods behind a service.

- `summarize_pod_logs(pod_name: str, namespace: str | None = None, tail_lines: int = 200)`  
  Returns a compact summary of pod logs.

- `summarize_service_logs(service_name: str, namespace: str | None = None, tail_lines_per_pod: int = 200)`  
  Returns a compact summary of service logs.

## Metrics

- `get_pod_metrics(pod_name: str, namespace: str | None = None)`  
  Returns pod metrics.

- `get_service_metrics(service_name: str, namespace: str | None = None)`  
  Returns service metrics.

- `get_pod_triage_metrics(pod_name: str, namespace: str | None = None)`  
  Returns cheaper triage-focused metrics for a pod.

- `get_service_triage_metrics(service_name: str, namespace: str | None = None)`  
  Returns cheaper triage-focused metrics for a service.

## Traces

- `get_trace_summaries(service_name: str, limit: int = 20, lookback: str = "15m", min_duration_ms: float | None = None, only_errors: bool = False)`  
  Returns summarized traces for a service.

- `get_trace_details(trace_id: str)`  
  Returns detailed information for a specific trace.

## Shell / kubectl

- `exec_shell(command: str)`  
  Executes a restricted shell command.

- `exec_kubectl(command: str)`  
  Executes a kubectl-only command.

- `get_shell_policy()`  
  Returns the active shell execution policy.

## Current backend-aware usage guidance

### Safe baseline tools
These are the safest starting tools in most runs:

- `get_backend_status`
- `get_cluster_overview`
- `get_pods_from_service`
- `get_services_from_pod`

### Use only when backend is available

- Prometheus-dependent:
  - `get_pod_metrics`
  - `get_service_metrics`
  - `get_pod_triage_metrics`
  - `get_service_triage_metrics`

- Jaeger-dependent:
  - `get_trace_summaries`
  - `get_trace_details`

- Neo4j-dependent:
  - `get_service_dependencies`
  - `get_services_used_by`
  - `get_service_map`
  - `get_service_topology_summary`

### Use carefully

- `exec_shell`
- `exec_kubectl`

---

## Project structure
```text
Kubernetes-Mcp/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── dependencies.py
│   └── server.py
│
├── clients/
│   ├── __init__.py
│   ├── base_k8s_client.py
│   ├── jaeger_client.py
│   ├── neo4j_client.py
│   ├── prometheus_client.py
│   └── shell_client.py
│
├── services/
│   ├── __init__.py
│   ├── logs_service.py
│   ├── metrics_service.py
│   ├── shell_service.py
│   ├── system_service.py
│   ├── topology_service.py
│   └── trace_service.py
│
├── tools/
│   ├── __init__.py
│   ├── logs.py
│   ├── metrics.py
│   ├── shell.py
│   ├── system.py
│   ├── topology.py
│   └── traces.py
│
├── utils/
│   ├── __init__.py
│   └── formatters.py
│
├── tests/
│   ├── __init__.py
│   └── smoke_test.py
│
├── .env.example
├── .gitignore
├── main.py
├── pyproject.toml
├── poetry.lock
└── README.md