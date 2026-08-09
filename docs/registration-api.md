# API de cadastros

As rotas abaixo são a base administrativa do Projeto Osiris. Elas já persistem
no PostgreSQL e devem ser usadas pela futura integração de WhatsApp e pelo painel.

| Método | Rota | Finalidade |
| --- | --- | --- |
| `POST` | `/api/v1/businesses` | Cadastra uma barbearia. |
| `GET` | `/api/v1/businesses/{business_id}` | Consulta uma barbearia. |
| `POST` | `/api/v1/businesses/{business_id}/barbers` | Cadastra um barbeiro. |
| `GET` | `/api/v1/businesses/{business_id}/barbers` | Lista barbeiros. |
| `POST` | `/api/v1/businesses/{business_id}/customers` | Cadastra um cliente. |
| `GET` | `/api/v1/businesses/{business_id}/customers` | Lista clientes. |

## Exemplo: cadastrar barbearia

```json
{
  "name": "Barbearia Osiris",
  "phone": "5511999999999",
  "timezone": "America/Sao_Paulo"
}
```

O telefone de uma barbearia é único. Para barbeiros e clientes, o telefone é
único apenas dentro da mesma barbearia.
