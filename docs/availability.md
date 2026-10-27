# Disponibilidade de horários

Somente inícios posteriores ao instante atual são oferecidos. A jornada usa o
fuso cadastrado na barbearia e a comparação usa UTC, independentemente do fuso
do servidor. Por exemplo, às 11:14, uma jornada com intervalos de 30 minutos
não oferece 11:00; o próximo início possível é 11:30, se estiver livre.

Datas passadas não retornam horários. Na página pública, horários expirados são
retirados a cada 15 segundos e ao voltar à página; se o horário selecionado
expirar, a seleção é limpa e o botão de confirmar é desabilitado. O formulário
também revalida o horário ao enviar. A API rejeita reserva ou reagendamento
público para um instante passado ou igual ao atual com HTTP 409, mesmo que a
página estivesse aberta antes de o horário expirar. Essa regra não impede o
registro administrativo de atendimentos históricos pelo proprietário.

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
