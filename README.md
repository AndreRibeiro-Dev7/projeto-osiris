# Projeto Osiris

Plataforma de atendimento e agendamento inteligente, iniciada para barbearias e preparada para evoluir para outros negócios que trabalham com agenda.

O objetivo do Osiris é conectar uma API de agendamentos a um agente de IA capaz de consultar horários, criar reservas e acompanhar o atendimento ao cliente.

![Documentação interativa da API do Projeto Osiris](./osiris-swagger-visao-geral.png)

## Status atual

O Osiris possui um **MVP operacional completo** para gestão de barbearias. O
fluxo principal foi validado de ponta a ponta:

```text
Horário livre → agendamento criado → horário removido
→ agendamento cancelado → horário liberado novamente
```

A aplicação já reúne painel do proprietário, agenda, clientes, equipe, catálogo
de serviços, agendamento público, assistente de IA e gestão financeira. A
implementação está coberta por **30 testes automatizados**.

## Funcionalidades implementadas

### Agenda e operação

- Cadastro de empresas, profissionais, serviços e clientes.
- Jornada semanal, folgas, bloqueios e duração individual por profissional.
- Disponibilidade calculada com prevenção de conflitos e tratamento de fuso.
- Criação, confirmação, conclusão e cancelamento de agendamentos.
- Agendamento público e reserva pela IA após confirmação do cliente.
- Agenda diária, histórico do cliente e acompanhamento de comparecimento.

### Painel e financeiro

- Painel responsivo com visão geral, indicadores e pendências importantes.
- Receitas, pagamentos, despesas fixas e variáveis, vencimentos e baixas.
- Comissões individuais por profissional.
- Metas mensais com compensação de superávit entre os meses.
- Gráficos financeiros com período, agrupamento, zoom e movimentação.
- Comparação de vários meses e relatório analítico escrito.
- Exportação de relatório financeiro formatado em Excel.

### Relacionamento e integrações

- Segmentação da carteira, fidelização, aniversários e histórico de clientes.
- Assistente baseado na OpenAI Responses API e nos dados reais da agenda.
- Confirmação de alteração de e-mail por código enviado pelo Resend.
- Estrutura preparada para WhatsApp e Google Calendar.

### Segurança e administração

- Login de proprietários com OAuth2 e tokens JWT com expiração.
- Senhas protegidas com Argon2 e dados isolados por barbearia.
- Configurações da empresa e da conta atualizadas pelo painel.
- Documentação interativa com OpenAPI/Swagger.

## Disponibilidade

A jornada de cada profissional é cadastrada por dia da semana. A API transforma essa jornada em intervalos de atendimento e remove os períodos que conflitam com agendamentos ativos (`scheduled` ou `confirmed`). Agendamentos cancelados não bloqueiam a agenda.

![Endpoint de consulta de disponibilidade](./osiris-swagger-disponibilidade.png)

Exemplo de configuração para segunda-feira, das 09:00 às 18:00, com atendimentos de 30 minutos:

```http
PUT /api/v1/businesses/{business_id}/barbers/{barber_id}/schedule/0
```

```json
{
  "starts_at": "09:00:00",
  "ends_at": "18:00:00",
  "slot_duration_minutes": 30
}
```

Consulta dos horários livres:

```http
GET /api/v1/businesses/{business_id}/barbers/{barber_id}/availability?appointment_date=2026-09-07
```

Exemplo resumido de resposta:

```json
{
  "appointment_date": "2026-09-07",
  "timezone": "America/Sao_Paulo",
  "slots": [
    {
      "starts_at": "2026-09-07T09:00:00-03:00",
      "ends_at": "2026-09-07T09:30:00-03:00"
    }
  ]
}
```

## Ciclo de vida do agendamento

![Endpoint de criação de agendamento](./osiris-swagger-agendamento.png)

| Operação | Endpoint | Regra |
| --- | --- | --- |
| Criar | `POST /api/v1/businesses/{business_id}/appointments` | Reserva um intervalo disponível |
| Consultar | `GET /api/v1/businesses/{business_id}/barbers/{barber_id}/appointments` | Lista agendamentos ativos na data |
| Confirmar | `PATCH /api/v1/businesses/{business_id}/appointments/{appointment_id}/confirm` | Permitido para `scheduled` |
| Cancelar | `PATCH /api/v1/businesses/{business_id}/appointments/{appointment_id}/cancel` | Permitido para `scheduled` ou `confirmed` |

Transições inválidas retornam `409 Conflict`; recursos inexistentes retornam `404 Not Found`.

## Arquitetura

O backend segue uma arquitetura em camadas:

```text
Requisição HTTP
    ↓
Rotas FastAPI
    ↓
Services (regras de negócio)
    ↓
Repositories (acesso a dados)
    ↓
PostgreSQL
```

Estrutura principal:

```text
app/
├── api/           # Endpoints e contratos HTTP
├── agents/        # Espaço para os agentes de IA
├── core/          # Configurações e exceções
├── database/      # Sessão e conexão assíncrona
├── integrations/  # Integrações externas
├── models/        # Entidades SQLAlchemy
├── repositories/  # Acesso a dados
├── schemas/       # Contratos Pydantic
└── services/      # Regras de negócio
```

## Tecnologias

- Python 3.12+
- FastAPI e OpenAPI
- PostgreSQL 16
- SQLAlchemy 2 (assíncrono)
- Alembic
- Docker Compose
- Pydantic
- OpenAI Responses API
- Pytest
- Ruff, Black e MyPy

## Executar localmente

```powershell
Copy-Item .env.example .env
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
docker compose up -d db
alembic upgrade head
fastapi dev app/main.py
```

Acesse:

- Painel do proprietário: `http://127.0.0.1:8000/dashboard/`
- Swagger: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/v1/health`
- Banco de dados: `http://127.0.0.1:8000/api/v1/health/database`

## Qualidade

```powershell
pytest
ruff check app tests
black --check app tests
mypy app tests
```

Estado registrado nesta entrega: **30 testes automatizados aprovados**.

## Próximos passos

O produto funcional está pronto. As próximas etapas são voltadas à publicação
e à operação comercial:

- Implantar aplicação e banco gerenciado com domínio próprio e HTTPS.
- Configurar backups automáticos e testar a restauração do banco.
- Adicionar logs centralizados, monitoramento e alertas de indisponibilidade.
- Concluir a integração oficial com WhatsApp e calendário.
- Usar domínio verificado para e-mails e implementar recuperação de senha.
- Ampliar testes de autorização, isolamento, interface e carga.
- Consolidar proteção de dados, auditoria e limites de requisição.
- Preparar onboarding, planos, cobrança e suporte ao cliente.

O roteiro detalhado está em
[Checklist para produção](./docs/production-checklist.md).
As instruções técnicas estão no
[Guia de publicação](./docs/deployment.md).
O repositório também inclui um `render.yaml` para a primeira homologação online.

## Autor

Desenvolvido por **André** como projeto de portfólio e estudo prático de APIs, arquitetura backend, regras de agendamento e agentes de IA.
