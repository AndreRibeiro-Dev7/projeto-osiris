# Carga moderada em homologação isolada

O cenário `tests/integration/test_load_database.py` exercita a aplicação ASGI
com PostgreSQL real. Prepara somente uma empresa, um proprietário, um barbeiro e
um serviço fictícios. Não aceita uma URL de produção: valida o host local, o nome
reservado do banco e a igualdade entre as variáveis de conexão antes de importar
o aplicativo.

## Executar

Com Docker Desktop aberto, no PowerShell da pasta do projeto:

```powershell
.\.venv-codex\Scripts\python.exe .\scripts\test_tenant_isolation.py --load
```

O script inicia um PostgreSQL temporário, aplica as migrações e executa somente
o cenário de carga. Usa uma porta vinculada a `127.0.0.1`, não cria volumes e remove
o contêiner ao terminar, inclusive quando um teste falha. E-mail, WhatsApp, Discord
e OpenAI ficam desabilitados. A execução sem `--load` continua executando os testes
funcionais anteriores; o novo teste fica pulado nesse modo.

## Perfil e critérios

Após uma consulta de aquecimento, são feitas 100 consultas, com no máximo dez
requisições em andamento. Elas alternam a apresentação pública da barbearia,
a disponibilidade e a agenda interna autenticada. Todas devem retornar HTTP 200
e dados coerentes com o estado inicial. O relatório apresenta p50, p95, máximo,
duração total e vazão. Os tempos individuais começam depois da espera pelo
semáforo; a duração total inclui o processamento de todas as consultas.

Na segunda fase, dez clientes fictícios disputam o mesmo horário. O teste exige:

- Uma resposta HTTP 201 e nove conflitos HTTP 409.
- Uma única reserva e um único cliente persistidos; as tentativas rejeitadas
  devem ter suas inserções desfeitas.
- Uma vaga a menos na disponibilidade após a disputa.

Cada fase tem um limite de 60 segundos para não permanecer presa indefinidamente.
O limite é uma proteção da execução, não uma meta de latência comercial. As
latências são medidas para comparação no mesmo ambiente, sem um corte arbitrário
que torne o CI dependente da velocidade do computador.

O GitHub Actions executa esse mesmo cenário no job `tenant-isolation` e inclui
o relatório dos testes aprovados nos logs.

## Limites e resultado

André executou o cenário em PostgreSQL temporário e apresentou o resultado:

| Medida | Resultado local |
| --- | --- |
| Consultas / concorrência máxima | 100 / 10 |
| Respostas HTTP 200 | 100 |
| p50 / p95 / máximo | 77,7 / 309,7 / 366,7 ms |
| Duração da fase de consultas | 1,04 s |
| Vazão nessa fase | 96,6 requisições/s |
| Disputa pelo mesmo horário | 1 reserva e 9 conflitos |
| Persistência após a disputa | 1 cliente, sem cadastros órfãos |
| Resultado do teste completo | 1 aprovado em 11,30 s |

O contêiner e o banco temporários foram removidos, sem volumes. Produção não foi
acessada. A aprovação desse cenário no GitHub Actions deve ser conferida após o push.

O transporte é ASGI dentro do processo: não mede navegador, TLS, rede externa,
proxy, servidor HTTP ou inicialização de instância no Render. O banco começa
vazio e o perfil tem uma duração curta. Portanto, esse resultado não determina
a capacidade do plano de produção, o número de barbearias suportadas ou o
comportamento com histórico extenso. Antes do lançamento comercial, ainda é
necessário um ensaio em homologação com volume de dados e infraestrutura
comparáveis ao uso esperado, além de conferir latências e consumo de recursos.
