"""Agent-mesh process manager — spawn, monitor, restart."""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess

from .config import MeshProcessConfig

logger = logging.getLogger(__name__)


class MeshProcess:
    """Manages the agent-mesh subprocess lifecycle."""

    def __init__(self, config: MeshProcessConfig, mesh_url: str) -> None:
        self._config = config
        self._mesh_url = mesh_url
        self._process: subprocess.Popen | None = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def spawn(self) -> bool:
        """Start agent-mesh if not already running. Returns True on success."""
        if self.is_running:
            return True

        cmd = self._resolve_command()
        if cmd is None:
            logger.error("agent-mesh binary not found: %s", self._config.command)
            return False

        args = [cmd, "--config", self._config.config]
        logger.info("spawning agent-mesh: %s", " ".join(args))

        try:
            self._process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                start_new_session=True,  # don't die with supervisor
            )
            logger.info("agent-mesh started (pid=%d)", self._process.pid)
            return True
        except OSError as e:
            logger.error("failed to start agent-mesh: %s", e)
            return False

    def stop(self) -> None:
        """Stop the managed agent-mesh process."""
        if self._process is None:
            return

        if self.is_running:
            logger.info("stopping agent-mesh (pid=%d)", self._process.pid)
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("agent-mesh did not stop, killing")
                self._process.kill()
                self._process.wait()

        self._process = None

    def check_and_restart(self) -> bool:
        """Check if process died and restart it. Returns True if running."""
        if self._process is None:
            return self.spawn()

        if self._process.poll() is not None:
            exit_code = self._process.returncode
            stderr_tail = ""
            if self._process.stderr:
                try:
                    stderr_tail = self._process.stderr.read(500).decode(errors="replace")
                except Exception:
                    pass
            logger.warning(
                "agent-mesh exited (code=%d)%s — restarting",
                exit_code,
                f": {stderr_tail.strip()}" if stderr_tail else "",
            )
            self._process = None
            return self.spawn()

        return True

    def _resolve_command(self) -> str | None:
        """Find the agent-mesh binary."""
        # Try as-is first (absolute path or in PATH)
        found = shutil.which(self._config.command)
        if found:
            return found
        # Common Go install location
        import os
        go_bin = os.path.expanduser(f"~/go/bin/{self._config.command}")
        if os.path.isfile(go_bin) and os.access(go_bin, os.X_OK):
            return go_bin
        return None

    async def wait_ready(self, timeout: float = 10.0) -> bool:
        """Wait until agent-mesh HTTP is responding."""
        import httpx

        deadline = asyncio.get_event_loop().time() + timeout
        async with httpx.AsyncClient() as client:
            while asyncio.get_event_loop().time() < deadline:
                try:
                    resp = await client.get(f"{self._mesh_url}/health")
                    if resp.status_code == 200:
                        logger.info("agent-mesh is ready")
                        return True
                except (httpx.ConnectError, httpx.ConnectTimeout):
                    pass
                await asyncio.sleep(0.5)

        logger.warning("agent-mesh did not become ready within %.0fs", timeout)
        return False
