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

### Resultado da homologação

Em 26 de outubro de 2026, o proprietário executou o programa no PowerShell e
apresentou a saída: `2 passed in 5.53s`. O PostgreSQL temporário recebeu todas as
migrações até `3d4e5f6a7b8c`. Foram aprovados o isolamento entre duas empresas e
seis contas e o fluxo público de cliente novo, conflito, confirmação,
reagendamento e cancelamento. O programa confirmou a remoção do container e do
banco temporários, sem criação de volumes.

Essa evidência valida o fluxo HTTP com banco real. A interação visual em celular
e o fluxo completo do assistente de IA continuam pendentes de homologação.

## Regressao visual da confirmacao de cancelamento

O job `booking-ui` executa `scripts/test_booking_dialog.cjs` em Chromium,
com larguras de 375 e 1280 pixels. As respostas da API usam dados ficticios;
nenhuma reserva real e alterada.

O teste verifica que a confirmacao comeca oculta, abre somente apos clicar em
cancelar, fecha com Voltar, Fechar ou Escape e envia exatamente uma requisicao
somente quando o cliente confirma o cancelamento. Tambem verifica que o modal
nao aparece ao abrir o formulario de um novo agendamento.

Em 27 de outubro de 2026, os dois cenarios passaram localmente no Chrome em
modo headless. A correcao aplica `display:none!important` aos elementos com
`hidden`, evitando que `display:grid` torne o modal visivel sem solicitacao.
O CSS tem uma nova versao na pagina para atualizar o cache dos navegadores.
