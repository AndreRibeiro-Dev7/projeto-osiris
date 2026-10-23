# Monitoramento e alertas

O GitHub Actions verifica a produção duas vezes por hora, aos minutos 7 e 37.
Esse intervalo permite detectar indisponibilidade sem manter continuamente ativa
a instância gratuita do Render.

São verificados:

- `/api/v1/health`, que confirma a disponibilidade da API;
- `/api/v1/health/database`, que confirma a conexão real com o PostgreSQL.

Cada endereço aceita até 120 segundos por tentativa e possui uma nova tentativa
para tolerar a inicialização lenta de uma instância suspensa.

## Comportamento do alerta

Quando qualquer verificação falha, o workflow:

1. registra o relatório na execução do GitHub Actions;
2. abre uma única ocorrência chamada `[Monitoramento] Osiris indisponivel`;
3. atribui a ocorrência ao proprietário do repositório;
4. mantém a execução marcada como falha.

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

Permanece pendente um teste controlado do ciclo de incidente: simular uma falha,
confirmar a abertura da ocorrência e depois validar o encerramento automático na
execução saudável seguinte. Esse teste não deve interromper a API de produção.

O acionamento manual oferece a opção `simulate_failure`. Quando marcada, ela não
consulta nem interrompe a produção: apenas percorre o mesmo fluxo de falha usado
pelo monitor, cria a ocorrência e deixa a execução vermelha de forma intencional.
Uma nova execução manual com a opção desmarcada valida API e banco e encerra a
ocorrência automaticamente.
