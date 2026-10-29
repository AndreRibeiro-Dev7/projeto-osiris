"""Exercise the Windows recovery script with a fake Docker command only."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell recovery procedure.")


def quote(value: Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
@pytest.mark.parametrize(
    "scenario",
    [
        "valid",
        "legacy",
        "missing",
        "malformed",
        "mismatch",
        "wrong-name",
        "restore-fails",
        "cleanup-fails",
    ],
)
def test_restore_integrity_and_cleanup(tmp_path: Path, shell: str, scenario: str) -> None:
    executable = shutil.which(shell)
    if not executable:
        pytest.skip(f"{shell} not installed")
    backup = tmp_path / "osiris-test.dump"
    backup.write_bytes(b"fictitious archive; never passed to actual Docker")
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    checksum = Path(str(backup) + ".sha256")
    if scenario not in {"legacy", "missing"}:
        checksum.write_text(
            (
                "invalid"
                if scenario == "malformed"
                else f"{'0' * 64 if scenario == 'mismatch' else digest}  "
                f"{'other.dump' if scenario == 'wrong-name' else backup.name}\n"
            ),
            encoding="ascii",
        )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "docker.ps1"
    journal = tmp_path / "commands.jsonl"
    fake.write_text(
        r"""
$entry = ConvertTo-Json -Compress -InputObject @($args)
Add-Content -LiteralPath $env:OSIRIS_FAKE_DOCKER_LOG -Value $entry
$global:LASTEXITCODE = 0
if ($args[0] -eq 'run') { Write-Output 'fake-container'; return }
if ($args[0] -eq 'rm') {
    if ($env:OSIRIS_FAKE_DOCKER_MODE -eq 'cleanup-fails') { $global:LASTEXITCODE = 1 }
    return
}
if ($args[0] -eq 'exec' -and $args[2] -eq 'pg_restore') {
    if ($env:OSIRIS_FAKE_DOCKER_MODE -eq 'restore-fails') { $global:LASTEXITCODE = 1 }
    return
}
if ($args[0] -eq 'exec' -and $args[2] -eq 'psql') {
    if ($args[-1] -like '*information_schema.tables*') { Write-Output '6' }
    else { Write-Output '1 | 1 | 5 | 80 | 9 | 25' }
}
""",
        encoding="utf-8",
    )
    runner = tmp_path / "run.ps1"
    strict = "-RequireChecksum" if scenario != "legacy" else ""
    runner.write_text(
        f"$env:PATH = {quote(bin_dir)} + [IO.Path]::PathSeparator + $env:PATH\n"
        f"if ((Get-Command docker).Source -ne {quote(fake)}) "
        "{ throw 'Fake Docker not selected' }\n"
        f"try {{ & {quote(ROOT / 'scripts/test_backup_restore.ps1')} "
        f"-BackupFile {quote(backup)} {strict} }}\n"
        "catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }\n",
        encoding="utf-8-sig",
    )
    environment = {
        **os.environ,
        "OSIRIS_FAKE_DOCKER_LOG": str(journal),
        "OSIRIS_FAKE_DOCKER_MODE": scenario,
    }
    # Let each PowerShell version discover its own built-in modules.
    environment.pop("PSModulePath", None)
    result = subprocess.run(
        [executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(runner)],
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
    )
    commands = (
        [json.loads(line) for line in journal.read_text().splitlines()] if journal.exists() else []
    )
    if scenario in {"missing", "malformed", "mismatch", "wrong-name"}:
        assert result.returncode != 0
        assert not commands, "Invalid integrity metadata must fail before starting Docker"
        expected = {
            "missing": "SHA-256 e obrigatorio",
            "malformed": "SHA-256 tem formato invalido",
            "mismatch": "SHA-256 divergente",
            "wrong-name": "SHA-256 pertence a outro arquivo",
        }
        assert expected[scenario] in result.stderr
    else:
        assert result.returncode == (
            1 if scenario in {"restore-fails", "cleanup-fails"} else 0
        ), result.stderr
        run = commands[0]
        assert run[0] == "run" and run[run.index("--network") + 1] == "none"
        assert run[run.index("--tmpfs") + 1] == "/var/lib/postgresql/data"
        assert not any(value in run for value in ("--publish", "-p"))
        assert any(value.endswith(":/backups:ro") for value in run)
        restore = next(
            command for command in commands if command[0] == "exec" and command[2] == "pg_restore"
        )
        assert "--single-transaction" in restore and "--exit-on-error" in restore
        assert commands[-1][:3] == ["rm", "--force", "--volumes"]
        if scenario == "cleanup-fails":
            assert "Nao foi possivel remover" in result.stderr
    assert backup.exists() and backup.read_bytes().startswith(b"fictitious archive")
