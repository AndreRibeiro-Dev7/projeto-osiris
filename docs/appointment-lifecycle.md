# Consulta e ciclo de vida do agendamento

## Consultar agenda de um barbeiro

`GET /api/v1/businesses/{business_id}/barbers/{barber_id}/appointments`

O parâmetro obrigatório `appointment_date` usa o formato `YYYY-MM-DD`. A API
interpreta essa data no fuso horário configurado para a barbearia e retorna
apenas agendamentos `scheduled` e `confirmed`.

## Alterar status

| Ação | Rota | Permitida quando |
| --- | --- | --- |
| Confirmar | `PATCH /businesses/{business_id}/appointments/{appointment_id}/confirm` | status é `scheduled` |
| Cancelar | `PATCH /businesses/{business_id}/appointments/{appointment_id}/cancel` | status é `scheduled` ou `confirmed` |

Ao cancelar, o horário deixa de bloquear novos agendamentos. Uma tentativa de
confirmar ou cancelar um agendamento em estado incompatível retorna `409 Conflict`.

## Homologação do agendamento público

O teste `tests/integration/test_public_booking_database.py` percorre as rotas
usadas pela página pública, sem login, usando PostgreSQL real e dados fictícios.
Ele verifica:

- carregamento da página, catálogo e horários disponíveis;
- criação de cliente novo e reserva com duração e preço do serviço;
- retirada do horário reservado da disponibilidade;
- rejeição de reserva sobreposta, sem deixar cliente ou agendamento incompleto;
- consulta pelo token, confirmação, reagendamento e liberação do horário anterior;
- cancelamento e liberação do novo horário;
- rejeição de confirmação e reagendamento após cancelamento e de token inexistente;
- nova reserva no horário liberado, reutilizando o cliente sem duplicá-lo.

Execute com o Docker Desktop aberto, na pasta do projeto:

```powershell
.\.venv-codex\Scripts\python.exe .\scripts\test_tenant_isolation.py
```

O programa agora executa os dois testes de integração: isolamento entre empresas
e fluxo público. O job `tenant-isolation` do GitHub Actions executa o mesmo
conjunto. O teste valida as rotas HTTP e os dados persistidos; a interação visual
da página em celular e o fluxo do assistente de IA têm homologações próprias.

A homologação pública deve ser registrada como aprovada somente após a execução
desse teste com PostgreSQL. A suíte local comum o pula quando não há banco de
integração configurado.
