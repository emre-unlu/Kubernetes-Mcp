from __future__ import annotations

import logging
import shlex
import subprocess
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


class ShellClient:
    """Restricted shell command executor.

    Responsibilities:
    - Validate commands against allow/block rules
    - Execute commands safely without shell=True
    - Enforce timeout
    - Return structured stdout/stderr/exit status
    """

    DEFAULT_ALLOWED_PREFIXES = [
        "kubectl",
        "helm",
        "ls",
        "cat",
        "grep",
        "ps",
        "env",
        "pwd",
        "head",
        "tail",
        "find",
        "awk",
        "sed",
    ]

    DEFAULT_BLOCKED_SUBSTRINGS = [
        "rm ",
        "rm-",
        " mv ",
        "chmod ",
        "chown ",
        "shutdown",
        "reboot",
        "poweroff",
        "mkfs",
        "dd ",
        "sudo ",
        "curl ",
        "wget ",
        "scp ",
        "sftp ",
        "nc ",
        "netcat ",
        "ssh ",
        "telnet ",
        "kill ",
        "killall ",
        "pkill ",
        ":(){:|:&};:",  # fork bomb
        ">",
        ">>",
        "|",
        "&&",
        "||",
        ";",
    ]

    def __init__(
        self,
        timeout_seconds: int = 20,
        allowed_prefixes: Optional[List[str]] = None,
        blocked_substrings: Optional[List[str]] = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.allowed_prefixes = allowed_prefixes or self.DEFAULT_ALLOWED_PREFIXES
        self.blocked_substrings = blocked_substrings or self.DEFAULT_BLOCKED_SUBSTRINGS

    def run(self, command: str) -> Dict[str, Any]:
        """Validate and execute a command safely."""
        cleaned = (command or "").strip()
        if not cleaned:
            raise ValueError("Command must not be empty")

        self._validate_command(cleaned)

        try:
            args = shlex.split(cleaned)
        except ValueError as exc:
            raise ValueError(f"Invalid shell syntax: {exc}") from exc

        if not args:
            raise ValueError("Command must not be empty after parsing")

        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
                shell=False,
            )
            return {
                "command": cleaned,
                "argv": args,
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as exc:
            logger.warning("Command timed out: %s", cleaned)
            return {
                "command": cleaned,
                "argv": args,
                "exit_code": None,
                "stdout": exc.stdout if exc.stdout else "",
                "stderr": exc.stderr if exc.stderr else "",
                "timed_out": True,
                "error": f"Command timed out after {self.timeout_seconds} seconds",
            }
        except FileNotFoundError as exc:
            logger.warning("Command binary not found: %s", cleaned)
            return {
                "command": cleaned,
                "argv": args,
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "error": f"Command not found: {args[0]}",
            }
        except Exception as exc:
            logger.exception("Unexpected shell execution failure")
            raise RuntimeError(f"Failed to execute command: {exc}") from exc

    def _validate_command(self, command: str) -> None:
        lowered = f" {command.lower()} "

        for blocked in self.blocked_substrings:
            if blocked.lower() in lowered:
                raise ValueError(f"Blocked command pattern detected: {blocked.strip()}")

        first_token = command.split(maxsplit=1)[0].lower()

        if first_token not in [prefix.lower() for prefix in self.allowed_prefixes]:
            raise ValueError(
                f"Command '{first_token}' is not in the allowed command list"
            )

    def get_policy(self) -> Dict[str, Any]:
        """Return the active execution policy for debugging/inspection."""
        return {
            "timeout_seconds": self.timeout_seconds,
            "allowed_prefixes": self.allowed_prefixes,
            "blocked_substrings": self.blocked_substrings,
        }