# Agente de atendimento

O primeiro agente do Projeto Osiris responde perguntas sobre horários livres e
coordena um fluxo seguro de agendamento com confirmação explícita.
Antes de chamar o modelo, a aplicação consulta a disponibilidade real no banco e
fornece somente a data, o fuso horário e os slots livres como contexto.

## Configuração

Defina no arquivo `.env`:

```text
OPENAI_API_KEY=sua-chave
OPENAI_MODEL=gpt-5.6-luna
```

Nunca envie a chave em uma requisição, registre-a em logs ou faça commit do
arquivo `.env`.

## Enviar uma mensagem

Use `POST /api/v1/businesses/{business_id}/assistant/messages`:

```json
{
  "barber_id": "0d15a1e1-31bd-437d-809f-71cfbe12569e",
  "appointment_date": "2026-09-07",
  "message": "Tem horário pela manhã?"
}
```

O agente responde em português brasileiro e oferece no máximo cinco opções. A IA
classifica a intenção por Structured Outputs, mas não grava agendamentos diretamente.
Toda proposta é validada contra a disponibilidade real e persistida no banco.

## Selecionar e confirmar um horário

Depois de consultar a disponibilidade, envie o cliente e o horário escolhido:

```json
{
  "barber_id": "0d15a1e1-31bd-437d-809f-71cfbe12569e",
  "customer_id": "fea93fe2-cbae-449b-b0f5-5d793e3ad4b2",
  "appointment_date": "2026-09-07",
  "message": "Quero às 10:30"
}
```

A resposta terá `action: "confirmation_required"` e um `conversation_id`. Para
concluir, envie uma nova mensagem repetindo esse identificador:

```json
{
  "barber_id": "0d15a1e1-31bd-437d-809f-71cfbe12569e",
  "appointment_date": "2026-09-07",
  "conversation_id": "identificador-retornado-na-etapa-anterior",
  "message": "Confirmo"
}
```

O servidor bloqueia a conversa, revalida o horário e somente então cria a reserva.
A resposta final usa `action: "booked"` e inclui `appointment_id`. Repetir a mesma
confirmação é idempotente e devolve o agendamento já criado.

Sem `OPENAI_API_KEY`, a rota retorna `503 Service Unavailable`. Se o provedor não
responder, retorna `502 Bad Gateway` sem expor detalhes internos.

## Homologação automatizada do fluxo

Execute com o Docker Desktop aberto, no ambiente Python do projeto:

```powershell
.\.venv-codex\Scripts\python.exe .\scripts\test_tenant_isolation.py
```

O programa executa três cenários em PostgreSQL temporário: isolamento entre
empresas, agendamento público e fluxo do assistente. O cenário do assistente usa
login, JWT, rotas, serviços, bloqueios de linha e persistência reais. Somente o
cliente do provedor de IA é substituído por respostas controladas, sem chamadas
externas nem consumo de créditos.

São verificados consulta de horários, cliente obrigatório, proposta sem reserva,
ausência de confirmação, confirmação repetida em paralelo, bloqueio posterior
por folga ou outra reserva, falha simulada do provedor e rollback diante de uma
interrupção na gravação. Uma reserva e seu vínculo com a conversa são salvos na
mesma transação; repetir a confirmação retorna a reserva já vinculada.

A confirmação bloqueia a conversa e o profissional, e reconsulta os horários
disponíveis antes de criar a reserva. Uma proposta que deixou de caber na agenda
retorna `409 Conflict`.

O job `tenant-isolation` do GitHub Actions executa os mesmos cenários. A suíte
local comum pula os testes de integração quando o banco temporário não foi
configurado. A homologação só deve ser marcada após a execução com PostgreSQL.

Essa verificação não comprova a interpretação de mensagens pelo modelo real,
suas respostas em linguagem natural nem a disponibilidade da conta no provedor.
Essa etapa requer uma validação separada com o provedor configurado.
