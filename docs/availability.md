# Disponibilidade de horários

## Configurar a jornada semanal

Use `PUT /api/v1/businesses/{business_id}/barbers/{barber_id}/schedule/{weekday}`.

O parâmetro `weekday` segue o padrão do Python: `0` representa segunda-feira e
`6` representa domingo. Exemplo para trabalhar às segundas, das 09:00 às 18:00,
com atendimentos de 30 minutos:

```json
{
  "starts_at": "09:00:00",
  "ends_at": "18:00:00",
  "slot_duration_minutes": 30
}
```

Envie uma configuração para cada dia em que o barbeiro trabalha. Repetir o
`PUT` para o mesmo barbeiro e dia substitui a configuração anterior.

## Consultar horários livres

Use `GET /api/v1/businesses/{business_id}/barbers/{barber_id}/availability` com
o parâmetro obrigatório `appointment_date` no formato `YYYY-MM-DD`.

A API gera os slots dentro da jornada daquele dia no fuso horário da barbearia.
Slots que se sobrepõem a agendamentos `scheduled` ou `confirmed` são removidos.
Agendamentos cancelados não bloqueiam horários. Um dia sem jornada configurada
retorna `slots: []`.

Exemplo de resposta:

```json
{
  "business_id": "b932827e-a7b0-46b2-9d9e-d30419f89777",
  "barber_id": "0d15a1e1-31bd-437d-809f-71cfbe12569e",
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
