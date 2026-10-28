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

## Validação adicional da agenda interna

O teste `tests/integration/test_scheduling_database.py` prepara uma empresa,
um proprietário, um barbeiro, um cliente e um serviço fictícios em PostgreSQL
temporário. Usa login real e chamadas HTTP, sem substituir permissões ou repositórios.

O cenário verifica:

- Configuração de expediente, pausa de almoço e disponibilidade nas bordas da pausa.
- Inclusão e remoção de folga, retirando e devolvendo horários da disponibilidade.
- Duas criações simultâneas no mesmo horário: uma aceita e outra recusada.
- Reservas adjacentes permitidas e reagendamento para horário ocupado recusado,
  preservando o horário original no banco.
- Reagendamento livre, confirmação, cancelamento e liberação do horário.
- Recusa de fechamento quando existem reservas ativas e bloqueio de novas reservas
  e reagendamentos para a data fechada.
- Dois reagendamentos concorrentes para o mesmo horário: um aceito e outro recusado.

A revisão identificou que o reagendamento interno não consultava o fechamento
da barbearia nem bloqueava o barbeiro de destino durante a disputa de horário.
Ambas as verificações foram adicionadas. A data de fechamento é interpretada
no fuso da barbearia, com teste unitário específico para a mudança de dia em UTC.

Esta cobertura de pausa e folga trata da disponibilidade calculada. Ela não
comprova que todos os caminhos de criação manual rejeitem intervalos fora dessa
disponibilidade; a API interna aceita intervalos manuais, enquanto o fluxo público
valida os horários oferecidos.

Para executar, com Docker Desktop iniciado:

```powershell
.\.venv-codex\Scripts\python.exe .\scripts\test_tenant_isolation.py
```

O script executa todos os testes de integração em um contêiner temporário, sem
volume e com porta somente local. André executou o cenário e apresentou o resultado:
**sete testes de integração aprovados em 12,80 segundos**, incluindo a agenda
interna. O contêiner e o banco temporários foram removidos, sem criação de volumes.
A suíte local também passou com 349 testes, além de lint, formatação e tipos.
Essa evidência conclui a homologação isolada; a aprovação no CI e a conferência
da versão publicada permanecem pendentes até o push.

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
