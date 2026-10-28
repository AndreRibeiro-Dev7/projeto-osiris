import os
import shlex
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


def test_production_monitor_tracks_latency_errors_and_database_health() -> None:
    workflow_path = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "uptime-monitor.yml"
    )
    workflow = workflow_path.read_text(encoding="utf-8")

    assert 'MAX_RESPONSE_TIME_SECONDS: "90"' in workflow
    assert r"%{http_code}\n%{time_total}" in workflow
    assert '"$BASE_URL/api/v1/health"' in workflow
    assert '"$BASE_URL/api/v1/health/database"' in workflow
    assert "latency_status" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "Open incident on failure" in workflow


@pytest.mark.skipif(sys.platform == "win32", reason="Executes the Linux GitHub Actions Bash step")
@pytest.mark.parametrize(
    ("scenario", "healthy", "attempts"),
    [
        ("recovered", True, 2),
        ("unavailable", False, 2),
        ("transport", False, 2),
        ("invalid-json", False, 1),
        ("slow", False, 1),
    ],
)
def test_monitor_evaluates_final_attempt(
    tmp_path: Path, scenario: str, healthy: bool, attempts: int
) -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("Bash is required to exercise the actual monitoring step")
    workflow = (
        Path(__file__).resolve().parents[1] / ".github/workflows/uptime-monitor.yml"
    ).read_text(encoding="utf-8")
    step = textwrap.dedent(
        workflow.split("        run: |\n", 1)[1].split("      - name: Open incident on failure", 1)[
            0
        ]
    )
    # Replace only external commands: execute the real workflow logic without
    # network access, waiting, or sending incident notifications.
    harness = r"""
    sleep() { :; }
    curl() {
      output=""
      while [ "$#" -gt 0 ]; do
        case "$1" in
          --output) output="$2"; shift 2 ;;
          *) url="$1"; shift ;;
        esac
      done
      code=200
      elapsed=0.2
      result=0
      body='{"status":"ok"}'
      if [[ "$url" != */database ]]; then
        count=0
        if [ -f calls ]; then count="$(cat calls)"; fi
        count=$((count + 1))
        echo "$count" > calls
        case "$SCENARIO" in
          recovered|unavailable)
            if [ "$SCENARIO" = unavailable ] || [ "$count" -eq 1 ]; then
              code=503; result=22; body='service unavailable'
              echo 'curl: (22) The requested URL returned error: 503' >&2
            fi ;;
          transport) code=000; result=6; body=''; echo 'DNS failure' >&2 ;;
          invalid-json) body='invalid JSON' ;;
          slow) elapsed=91 ;;
        esac
      fi
      printf '%s' "$body" > "$output"
      printf '\n%s\n%s' "$code" "$elapsed"
      return "$result"
    }
    """
    python = shlex.quote(Path(sys.executable).as_posix())
    script = f'python() {{ {python} "$@"; }}\n' + textwrap.dedent(harness) + step
    completed = subprocess.run(
        [bash, "-c", script],
        cwd=tmp_path,
        env={
            **os.environ,
            "RUNNER_TEMP": ".",
            "GITHUB_OUTPUT": "output.txt",
            "GITHUB_STEP_SUMMARY": "summary.txt",
            "BASE_URL": "https://monitor.invalid",
            "MAX_RESPONSE_TIME_SECONDS": "90",
            "MONITOR_MODE": "health-check",
            "SCENARIO": scenario,
        },
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    output = (tmp_path / "output.txt").read_text(encoding="utf-8")
    assert f"healthy={str(healthy).lower()}\n" in output
    assert int((tmp_path / "calls").read_text()) == attempts
    assert "Banco: saudavel" in output
    if healthy:
        assert "API: saudavel (HTTP 200" in output
        assert "503" not in output
    else:
        assert "API: falha" in output
