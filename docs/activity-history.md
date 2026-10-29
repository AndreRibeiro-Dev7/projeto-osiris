# Histórico de atividades e falhas de auditoria

O painel Atividades consulta `GET /api/v1/businesses/{business_id}/audit-logs`.
Proprietário principal e coproprietários podem consultar o histórico da própria
barbearia. Profissionais, visitantes sem login e contas de outra empresa não têm
esse acesso. A consulta aceita filtro por área e limite de 1 a 200 registros.

## Registro das ações

As alterações autenticadas com resposta de sucesso registram área, descrição,
método, caminho, data e um retrato da conta que realizou a ação: identificador,
e-mail, função e condição de proprietário principal. O histórico não copia o corpo
das requisições, senhas, tokens ou detalhes livres da despesa.

O identificador do autor torna-se nulo quando uma conta de coproprietário é
excluída. O e-mail e a função registrados no momento da ação permanecem para
preservar a autoria. Esses dados pessoais são acessíveis somente nas consultas
autorizadas; sua política de retenção ainda precisa ser definida separadamente.

As descrições agora identificam a remoção de folga e de dia da jornada. Uma
consulta de horários ao assistente não gera uma falsa alteração no sistema.
Quando o assistente retorna uma reserva confirmada, a API informa explicitamente
ao mecanismo de auditoria que deve registrar a confirmação na área Agenda.
Repetições idempotentes podem registrar novas confirmações da mesma reserva;
o número de entradas não representa o número de reservas distintas.

## Quando o registro falha

A ação principal e seu histórico usam transações separadas. O mecanismo atual
não é uma auditoria atômica ou uma fila de reprocessamento: pode haver uma ação
salva sem a correspondente entrada se a persistência do histórico falhar.

Nessa situação, a API preserva a resposta da ação já concluída e emite o evento
`audit.persistence_failed`, com identificador da requisição e modelo da rota.
Tenta também o alerta operacional `audit_persistence_failed`, na categoria
integração, usando o canal e a deduplicação existentes. O código HTTP informado
nesse alerta pertence à ação original, que pode ter sido bem-sucedida.

Se a notificação também falhar de forma inesperada, o evento `audit.alert_failed`
é registrado e a resposta original continua preservada. Isso evita apresentar
uma ação salva como se precisasse ser repetida. O alerta não recupera nem cria
automaticamente a entrada ausente: o responsável deve investigar pelo request ID.

Esses caminhos não registram o texto bruto nem o traceback da exceção, que podem
conter parâmetros pessoais. Falhas de entrega ao Discord também passam a ser
registradas sem a exceção HTTP que poderia incluir o token do webhook.

## Validação em 29/10/2026

Os testes locais verificam descrições, consultas sem falsa mutação, registro de
reserva confirmada pelo assistente, resposta preservada quando a auditoria falha
e ausência de dados da exceção nos logs. A suíte local passou com 374 testes;
16 cenários dependentes de PostgreSQL ou Linux ficaram pulados. Lint, formatação
e tipos também foram aprovados.

O teste `tests/integration/test_audit_database.py` usa banco e autenticação reais
com contas fictícias. Verifica cadastro, pagamento e exclusão de despesa;
conclusão de atendimento; filtro e limite; impedimento de consulta por outra
empresa ou profissional; inexistência de rotas de edição e exclusão do histórico;
e preservação da autoria depois de excluir o coproprietário. Também simula falha
de auditoria e confere que a despesa principal permaneceu salva. O cenário do
assistente foi ampliado para conferir suas entradas de confirmação.

```powershell
& ".\.venv-codex\Scripts\python.exe" ".\scripts\test_tenant_isolation.py"
```

André executou a homologação em PostgreSQL temporário: 10 testes aprovados e
1 ignorado em 24,12 segundos. O cenário de carga opcional ficou fora dessa execução.
Foram validados autoria, financeiro, filtros, preservação após excluir o
coproprietário e resposta preservada na falha simulada de auditoria.
O container e o banco temporários foram removidos sem criação de volume.
A publicação desta revisão ainda está pendente.
Nenhuma falha foi provocada em produção e as notificações dos testes são simuladas.
Não há nova migração nesta etapa. A API não oferece edição ou exclusão de entradas;
isso não impede alterações por alguém com acesso administrativo direto ao banco.
