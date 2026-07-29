# Ambiente de desenvolvimento

## Pré-requisitos

- Git 2.40+
- Python 3.12+
- Docker Desktop, com Docker Compose habilitado

Confirme após a instalação:

```powershell
git --version
py -3.12 --version
docker --version
docker compose version
```

## Identidade do Git

Antes do primeiro commit, configure a identidade que deve aparecer no histórico:

```powershell
git config --global user.name "Seu nome"
git config --global user.email "seu-email@exemplo.com"
```

Use o e-mail vinculado à sua conta do GitHub ou o endereço `noreply` oferecido
por ela, se preferir manter o e-mail pessoal privado.

## Preparar o projeto

Na raiz do repositório:

```powershell
Copy-Item .env.example .env
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Verificação local

```powershell
ruff check .
black --check .
mypy app
pytest
fastapi dev app/main.py
```

A documentação interativa estará em `http://127.0.0.1:8000/docs`.

## Banco via Docker

```powershell
docker compose up --build
```

O PostgreSQL é exposto em `localhost:5432` para desenvolvimento. As credenciais
iniciais estão em `.env.example` e só devem ser usadas localmente.
