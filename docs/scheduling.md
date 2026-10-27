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

## Consulta pelo cliente na página pública

Após reservar, o cliente pode abrir **Gerenciar minha reserva** na própria página.
Ao voltar à página da mesma barbearia, **Meus agendamentos** mostra os acessos
lembrados naquele navegador. Confirmar presença continua sendo uma ação explícita;
guardar o acesso não confirma nem altera a reserva.

O navegador armazena até 20 acessos por barbearia em `localStorage`, com o token
da reserva, serviço, profissional, data e último estado conhecido. Nome e telefone
do cliente não são armazenados nessa lista. Cada abertura consulta o estado atual
na API; as alterações continuam exigindo o token público da reserva. Não há busca
de reservas por telefone sem verificação de identidade.

**Remover acessos salvos** apaga somente a lista daquele navegador, sem cancelar
reservas. Em navegação privada, após limpar os dados ou em outro aparelho, a lista
pode não estar disponível. O acesso por link permanece como alternativa opcional
em **Usar em outro aparelho**, e os links antigos continuam válidos. Se o navegador
bloquear o armazenamento, a página avisa e oferece essa alternativa imediatamente.

O teste `scripts/test_booking_dialog.cjs` verifica criação, consulta na mesma
página, confirmação, retorno à lista, separação das listas por barbearia,
cancelamento, remoção local e falha de armazenamento em celular e computador.
