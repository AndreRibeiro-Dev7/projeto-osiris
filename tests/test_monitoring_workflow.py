from pathlib import Path


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
