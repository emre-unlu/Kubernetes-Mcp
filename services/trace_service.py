from __future__ import annotations

from typing import Any, Dict, List, Optional

from clients.jaeger_client import JaegerClient


class TraceService:
    def __init__(self, jaeger_client: JaegerClient) -> None:
        self.jaeger_client = jaeger_client

    def get_trace_summaries(
        self,
        service_name: str,
        limit: int = 20,
        lookback: str = "15m",
        min_duration_ms: Optional[float] = None,
        only_errors: bool = False,
    ) -> Dict[str, Any]:
        raw_response = self.jaeger_client.search_traces(
            service=service_name,
            limit=limit,
            lookback=lookback,
            min_duration_ms=min_duration_ms,
            only_errors=only_errors,
        )

        traces = self.jaeger_client.extract_trace_list(raw_response)

        results: Dict[str, Any] = {
            "service": service_name,
            "lookback": lookback,
            "limit": limit,
            "only_errors": only_errors,
            "traces": [],
            "traces_count": 0,
        }

        if not traces:
            results["info"] = (
                f"No traces found for service '{service_name}' in lookback '{lookback}'."
            )
            return results

        for trace in traces:
            summary = self._summarize_trace(trace)
            if summary:
                results["traces"].append(summary)

        results["traces"].sort(key=lambda item: item["latency_ms"], reverse=True)
        results["traces_count"] = len(results["traces"])
        return results

    def get_trace_details(self, trace_id: str) -> Dict[str, Any]:
        raw_response = self.jaeger_client.get_trace(trace_id)
        trace = self.jaeger_client.extract_single_trace(raw_response)

        if trace is None:
            return {
                "trace_id": trace_id,
                "error": f"No trace found with ID '{trace_id}'.",
            }

        return {
            "trace_id": trace_id,
            "summary": self._summarize_trace(trace),
            "spans": self._extract_spans(trace),
            "raw_trace": trace,
        }

    def _summarize_trace(self, trace: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        spans: List[Dict[str, Any]] = trace.get("spans", [])
        processes: Dict[str, Dict[str, Any]] = trace.get("processes", {})

        if not spans:
            return None

        root_span = self._find_root_span(spans)
        if root_span is None:
            return None

        latency_ms = root_span.get("duration", 0) / 1000.0
        service_map = {
            process_id: process_info.get("serviceName", "unknown")
            for process_id, process_info in processes.items()
        }

        sorted_spans = sorted(spans, key=lambda item: item.get("startTime", 0))

        service_sequence: List[str] = []
        last_service: Optional[str] = None
        for span in sorted_spans:
            service_name = service_map.get(span.get("processID"), "unknown")
            if service_name != last_service:
                service_sequence.append(service_name)
                last_service = service_name

        has_error, error_messages = self._extract_errors(sorted_spans)

        summary: Dict[str, Any] = {
            "trace_id": trace.get("traceID"),
            "root_operation": root_span.get("operationName"),
            "latency_ms": latency_ms,
            "has_error": has_error,
            "service_sequence": service_sequence,
            "service_path": " -> ".join(service_sequence),
            "span_count": len(spans),
        }

        if has_error:
            summary["error_messages"] = error_messages

        return summary

    def _extract_spans(self, trace: Dict[str, Any]) -> List[Dict[str, Any]]:
        spans: List[Dict[str, Any]] = trace.get("spans", [])
        processes: Dict[str, Dict[str, Any]] = trace.get("processes", {})

        service_map = {
            process_id: process_info.get("serviceName", "unknown")
            for process_id, process_info in processes.items()
        }

        cleaned_spans: List[Dict[str, Any]] = []
        for span in sorted(spans, key=lambda item: item.get("startTime", 0)):
            references = span.get("references", [])
            parent_span_id = None
            for ref in references:
                if ref.get("refType") == "CHILD_OF":
                    parent_span_id = ref.get("spanID")
                    break

            has_error, error_messages = self._extract_errors([span])

            cleaned_spans.append(
                {
                    "span_id": span.get("spanID"),
                    "parent_span_id": parent_span_id,
                    "service": service_map.get(span.get("processID"), "unknown"),
                    "operation": span.get("operationName"),
                    "start_time": span.get("startTime"),
                    "duration_ms": span.get("duration", 0) / 1000.0,
                    "has_error": has_error,
                    "error_messages": error_messages if has_error else [],
                    "tags": span.get("tags", []),
                }
            )

        return cleaned_spans

    @staticmethod
    def _find_root_span(spans: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for span in spans:
            if not span.get("references"):
                return span
        return None

    @staticmethod
    def _extract_errors(spans: List[Dict[str, Any]]) -> tuple[bool, List[str]]:
        has_error = False
        error_messages: List[str] = []

        for span in spans:
            is_error_span = False

            for tag in span.get("tags", []):
                if tag.get("key") == "error" and tag.get("value") is True:
                    has_error = True
                    is_error_span = True
                    break

            if not is_error_span:
                continue

            for log in span.get("logs", []):
                fields = {
                    field.get("key"): field.get("value")
                    for field in log.get("fields", [])
                }

                if fields.get("event") == "error":
                    if "message" in fields and fields["message"]:
                        error_messages.append(str(fields["message"]))
                    if "stack" in fields and fields["stack"]:
                        first_line = str(fields["stack"]).splitlines()[0]
                        error_messages.append(first_line)

        # deduplicate while preserving order
        deduped = list(dict.fromkeys(error_messages))
        return has_error, deduped