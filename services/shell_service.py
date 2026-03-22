from __future__ import annotations

from typing import Any, Dict, Optional

from clients.shell_client import ShellClient


class ShellService:
    """Service layer for controlled shell execution.

    Responsibilities:
    - Delegate command execution to ShellClient
    - Enforce service-level policy if needed
    - Truncate oversized outputs
    - Return structured, LLM-friendly results
    """

    def __init__(
        self,
        shell_client: ShellClient,
        max_output_chars: int = 12000,
    ) -> None:
        self.shell_client = shell_client
        self.max_output_chars = max_output_chars

    def exec_shell(
        self,
        command: str,
    ) -> Dict[str, Any]:
        """Execute a validated shell command and normalize the result."""
        result = self.shell_client.run(command)

        stdout = result.get("stdout", "") or ""
        stderr = result.get("stderr", "") or ""

        truncated_stdout = self._truncate_text(stdout)
        truncated_stderr = self._truncate_text(stderr)

        normalized: Dict[str, Any] = {
            "command": result.get("command"),
            "argv": result.get("argv"),
            "exit_code": result.get("exit_code"),
            "timed_out": result.get("timed_out", False),
            "stdout": truncated_stdout["text"],
            "stderr": truncated_stderr["text"],
            "stdout_truncated": truncated_stdout["truncated"],
            "stderr_truncated": truncated_stderr["truncated"],
        }

        if "error" in result:
            normalized["error"] = result["error"]

        normalized["success"] = (
            normalized.get("exit_code") == 0
            and not normalized.get("timed_out", False)
            and "error" not in normalized
        )

        normalized["summary"] = self._build_summary(normalized)
        return normalized

    def exec_kubectl(
        self,
        command: str,
    ) -> Dict[str, Any]:
        """Execute a kubectl command only."""
        cleaned = (command or "").strip()
        if not cleaned.startswith("kubectl "):
            return {
                "command": cleaned,
                "success": False,
                "error": "Only kubectl commands are allowed for exec_kubectl.",
            }

        return self.exec_shell(cleaned)

    def get_shell_policy(self) -> Dict[str, Any]:
        """Expose the active shell policy."""
        policy = self.shell_client.get_policy()
        policy["max_output_chars"] = self.max_output_chars
        return policy

    def _truncate_text(self, text: str) -> Dict[str, Any]:
        if len(text) <= self.max_output_chars:
            return {
                "text": text,
                "truncated": False,
            }

        return {
            "text": text[: self.max_output_chars] + "\n...[truncated]",
            "truncated": True,
        }

    @staticmethod
    def _build_summary(result: Dict[str, Any]) -> Dict[str, Any]:
        stdout = result.get("stdout", "") or ""
        stderr = result.get("stderr", "") or ""

        return {
            "stdout_line_count": len(stdout.splitlines()) if stdout else 0,
            "stderr_line_count": len(stderr.splitlines()) if stderr else 0,
            "has_stdout": bool(stdout.strip()),
            "has_stderr": bool(stderr.strip()),
            "success": result.get("success", False),
            "timed_out": result.get("timed_out", False),
        }