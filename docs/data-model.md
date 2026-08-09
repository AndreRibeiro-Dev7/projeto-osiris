# Modelo de dados inicial

## Entidades

| Entidade | Papel |
| --- | --- |
| `businesses` | Uma barbearia atendida pela plataforma. |
| `barbers` | Profissionais vinculados a uma barbearia. |
| `customers` | Clientes de uma barbearia. |
| `appointments` | Reserva de um intervalo para um cliente com um barbeiro. |

## Relacionamentos

```text
Business 1 ── N Barber
Business 1 ── N Customer
Business 1 ── N Appointment
Barber   1 ── N Appointment
Customer 1 ── N Appointment
```

## Regras no banco

- Telefones de barbeiros e clientes são únicos dentro da mesma barbearia.
- Um agendamento exige barbearia, barbeiro, cliente, início e fim.
- `ends_at` deve ser posterior a `starts_at`.
- Agendamentos são indexados por barbeiro/data e barbearia/data para consultas de agenda.

O serviço de agendamento, que será criado depois, validará regras que envolvem
várias linhas, como impedir horários sobrepostos para o mesmo barbeiro.
