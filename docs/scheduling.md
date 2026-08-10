# Regras de agendamento

## Criar agendamento

`POST /api/v1/businesses/{business_id}/appointments` recebe o barbeiro, o
cliente e o intervalo desejado. Datas devem incluir fuso horário no formato ISO
8601, por exemplo `2026-08-10T10:00:00-03:00`.

```json
{
  "barber_id": "UUID do barbeiro",
  "customer_id": "UUID do cliente",
  "starts_at": "2026-08-10T10:00:00-03:00",
  "ends_at": "2026-08-10T10:30:00-03:00",
  "notes": "Corte e barba"
}
```

## Regras aplicadas

1. A barbearia, o barbeiro e o cliente precisam existir.
2. Barbeiro e cliente devem pertencer à barbearia informada.
3. O barbeiro precisa estar ativo.
4. O horário final precisa ser posterior ao inicial.
5. Um barbeiro não pode ter dois agendamentos `scheduled` ou `confirmed` que se
   sobreponham.

Durante a decisão, a linha do barbeiro é bloqueada na transação. Isso faz duas
requisições simultâneas para o mesmo barbeiro serem avaliadas uma de cada vez.
