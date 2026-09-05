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
