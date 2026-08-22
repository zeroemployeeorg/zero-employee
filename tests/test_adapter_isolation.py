"""A4: core wheel and CLI import without Node or the Sandcastle adapter module."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_cli_imports_without_loading_sandcastle_adapter_or_node():
    env = {**os.environ, "PATH": "/usr/bin:/bin", "PYTHONPATH": str(_ROOT / "src")}
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import zero_employee.cli; "
                "assert 'zero_employee.adapters.sandcastle' not in sys.modules; "
                "print('ok')"
            ),
        ],
        capture_output=True,
        text=True,
        cwd=str(_ROOT),
        env=env,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "ok" in proc.stdout
