# Projeto Osiris

Plataforma de agentes de IA para atendimento e agendamento. A primeira versão
atende barbearias por WhatsApp e foi desenhada para evoluir para outros negócios
que dependem de agenda.

## Stack

- Python 3.12+
- FastAPI
- PostgreSQL 16
- SQLAlchemy 2 e Alembic
- Docker Compose
- Pytest, Ruff, Black e MyPy

## Estrutura

```text
app/
  api/             # Endpoints e contratos HTTP
  agents/          # Orquestração de agentes de IA
  core/            # Configuração e componentes transversais
  database/        # Conexão e sessão do banco
  integrations/    # Adaptadores de provedores externos
  models/          # Entidades persistidas
  repositories/    # Acesso a dados
  schemas/         # Modelos Pydantic
  services/        # Casos de uso
docs/              # Arquitetura e decisões técnicas
tests/             # Testes automatizados
```

## Executar localmente

1. Instale Python 3.12+ e Docker Desktop.
2. Crie o arquivo de ambiente: `Copy-Item .env.example .env`.
3. Crie e ative o ambiente virtual:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Instale o projeto: `python -m pip install -e ".[dev]"`.
5. Inicie a API: `fastapi dev app/main.py`.
6. Acesse `http://127.0.0.1:8000/docs` e `http://127.0.0.1:8000/api/v1/health`.

## Executar com Docker

```powershell
Copy-Item .env.example .env
docker compose up --build
```

## Qualidade

```powershell
ruff check .
black --check .
mypy app
pytest
```

## Documentação

- [Arquitetura inicial](docs/architecture.md)
- [ADR 0001 — arquitetura em camadas](docs/adr/0001-layered-architecture.md)
- [Configuração do ambiente](docs/development-setup.md)
- [Modelo de dados inicial](docs/data-model.md)
- [API de cadastros](docs/registration-api.md)
- [Regras de agendamento](docs/scheduling.md)
