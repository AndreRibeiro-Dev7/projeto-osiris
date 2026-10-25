# Monitoramento e alertas

O GitHub Actions verifica a produção duas vezes por hora, aos minutos 7 e 37.
Esse intervalo permite detectar indisponibilidade sem manter continuamente ativa
a instância gratuita do Render.

São verificados:

- `/api/v1/health`, que confirma a disponibilidade da API;
- `/api/v1/health/database`, que confirma a conexão real com o PostgreSQL.

O relatório de cada execução registra o código HTTP e o tempo total de resposta
dos dois endpoints. Uma resposta acima de 90 segundos é tratada como falha para
detectar degradação antes que a plataforma fique totalmente indisponível. O
resumo fica visível na própria execução do GitHub Actions.

Cada endereço aceita até 120 segundos por tentativa e possui uma nova tentativa
para tolerar a inicialização lenta de uma instância suspensa.

## Comportamento do alerta

Quando qualquer verificação falha, o workflow:

1. registra o relatório na execução do GitHub Actions;
2. abre uma única ocorrência chamada `[Monitoramento] Osiris indisponivel`;
3. atribui a ocorrência ao proprietário do repositório;
4. mantém a execução marcada como falha.

Erros de rede, respostas diferentes de HTTP 200, JSON inválido, estado diferente
de `ok`, lentidão acima do limite e falhas de conexão com o banco percorrem o
mesmo fluxo de incidente.

Não são criadas ocorrências duplicadas enquanto a primeira estiver aberta. Na
primeira verificação saudável, o monitor comenta a recuperação e encerra a
ocorrência automaticamente.

O workflow usa somente o `GITHUB_TOKEN` temporário, limitado a leitura do código
e escrita em ocorrências. Nenhuma credencial do Render ou do banco é utilizada.

## Ativação e teste

Depois de enviar o arquivo `.github/workflows/uptime-monitor.yml` para a branch
`main`, abra **GitHub → Actions → Production uptime monitor → Run workflow**.
A primeira execução deve ficar verde.

Para receber o alerta por e-mail ou pelo aplicativo, mantenha habilitadas as
notificações de ocorrências atribuídas à sua conta nas configurações do GitHub.

Os agendamentos do GitHub Actions podem sofrer alguns minutos de atraso em
períodos de alta demanda. O monitor é uma camada adicional aos health checks e
reinícios automáticos já executados pelo Render.

## Validação em produção

Em 23 de outubro de 2026, as três primeiras execuções agendadas foram concluídas
com sucesso. Cada execução confirmou a disponibilidade da API e a conexão com o
banco em aproximadamente 40 a 50 segundos.

No mesmo dia, o ciclo de incidente também foi validado sem interromper a API de
produção. A execução manual `#5`, em modo `simulate-failure`, abriu a ocorrência
`#1` e terminou com falha intencional. A execução `#6`, em modo `health-check`,
validou API e banco, publicou a recuperação e encerrou a ocorrência
automaticamente.

O acionamento manual oferece o seletor `run_mode`. Para testar o alerta, escolha
`simulate-failure`. Esse modo não consulta nem interrompe a produção: apenas
percorre o mesmo fluxo de falha usado pelo monitor, cria a ocorrência e deixa a
execução vermelha de forma intencional. Depois, execute novamente escolhendo
`health-check`; essa opção valida API e banco e encerra a ocorrência
automaticamente.
