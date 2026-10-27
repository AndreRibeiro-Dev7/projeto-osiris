"""Run real-database tenant checks in a disposable, loopback-only PostgreSQL."""

from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def find_docker() -> str:
    candidates = [shutil.which("docker")]
    for variable, suffix in (
        ("LOCALAPPDATA", "Programs/DockerDesktop/resources/bin/docker.exe"),
        ("ProgramFiles", "Docker/Docker/resources/bin/docker.exe"),
    ):
        if os.environ.get(variable):
            candidates.append(str(Path(os.environ[variable]) / suffix))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("Docker nao encontrado. Abra o Docker Desktop e tente novamente.")


def docker_command(
    docker: str, *arguments: str, env: dict[str, str]
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [docker, *arguments], env=env, text=True, capture_output=True, timeout=120, check=False
    )


def main() -> int:
    docker = find_docker()
    identifier = uuid4().hex
    container = f"osiris-isolation-test-{identifier}"
    database = f"osiris_isolation_test_{identifier}"
    password = secrets.token_hex(24)
    environment = {
        **os.environ,
        "POSTGRES_PASSWORD": password,
        "JWT_SECRET_KEY": secrets.token_hex(32),
        "ENVIRONMENT": "development",
        "API_V1_PREFIX": "/api/v1",
        "DEBUG": "false",
        "LOG_LEVEL": "WARNING",
        "DATABASE_ECHO": "false",
        "OWNER_BOOTSTRAP_ENABLED": "false",
        "EMAIL_DELIVERY_ENABLED": "false",
        "DISCORD_ALERT_WEBHOOK_URL": "",
        "OPENAI_API_KEY": "",
        "RESEND_API_KEY": "",
    }
    created = False
    try:
        print("Iniciando PostgreSQL temporario para duas barbearias ficticias...", flush=True)
        result = docker_command(
            docker,
            "run",
            "--detach",
            "--rm",
            "--name",
            container,
            "--label",
            "osiris.test=tenant-isolation",
            "--publish",
            "127.0.0.1::5432",
            "--env",
            "POSTGRES_PASSWORD",
            "--env",
            f"POSTGRES_DB={database}",
            "postgres:16-alpine",
            env=environment,
        )
        if result.returncode:
            raise RuntimeError("Nao foi possivel iniciar o container de teste.")
        created = True
        for _ in range(30):
            result = docker_command(
                docker, "exec", container, "pg_isready", "-U", "postgres", env=environment
            )
            if result.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("O PostgreSQL temporario nao ficou pronto.")

        result = docker_command(docker, "port", container, "5432/tcp", env=environment)
        address = result.stdout.strip()
        host, _, port = address.rpartition(":")
        if result.returncode or host != "127.0.0.1" or not port.isdigit():
            raise RuntimeError("Nao foi possivel identificar a porta local do teste.")
        environment["DATABASE_URL"] = (
            f"postgresql+asyncpg://postgres:{password}@127.0.0.1:{port}/{database}"
        )
        environment["OSIRIS_INTEGRATION_DATABASE_URL"] = environment["DATABASE_URL"]
        for arguments in (
            ["-m", "alembic", "upgrade", "head"],
            ["-m", "pytest", "tests/integration", "-p", "no:cacheprovider"],
        ):
            result = subprocess.run(
                [sys.executable, *arguments], cwd=ROOT, env=environment, check=False, timeout=180
            )
            if result.returncode:
                return result.returncode
        print("Isolamento validado em PostgreSQL: duas empresas e seis contas ficticias.")
        print(
            "Fluxo publico validado: cliente novo, conflito, "
            "confirmacao, reagendamento e cancelamento."
        )
        print(
            "Assistente validado com modelo simulado: confirmacao, "
            "repeticao concorrente, rollback e indisponibilidade."
        )
        return 0
    finally:
        if created:
            result = docker_command(docker, "rm", "--force", container, env=environment)
            if result.returncode:
                raise RuntimeError(f"Remova o container temporario manualmente: {container}")
            print("Container e banco temporarios removidos. Nenhum volume foi criado.")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(str(error))
        raise SystemExit(1) from None
    except (OSError, subprocess.TimeoutExpired) as error:
        # Do not print subprocess arguments or environment values containing credentials.
        print(f"Homologacao nao concluida ({type(error).__name__}). Verifique o Docker Desktop.")
        raise SystemExit(1) from None
