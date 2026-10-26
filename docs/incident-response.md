# Resposta a incidentes

Este procedimento deve ser usado quando o Osiris emitir um alerta ou quando um
usuário comunicar indisponibilidade, erro recorrente ou risco de perda de dados.
O objetivo é restaurar a operação com segurança, preservar evidências técnicas e
manter o proprietário informado.

## Responsabilidade e canais

O **proprietário principal** é o responsável inicial por reconhecer o alerta,
coordenar a resposta e encerrar o incidente. Ele pode delegar a investigação,
mas continua responsável pela decisão de restauração, rollback ou comunicação
aos usuários.

Os canais oficiais são:

- o canal privado do Discord configurado em `DISCORD_ALERT_WEBHOOK_URL`, para
  alertas operacionais de login, e-mail, IA e integrações;
- a ocorrência automática `[Monitoramento] Osiris indisponivel` no GitHub, para
  indisponibilidade ou degradação da API e do banco;
- os logs do Render e a execução do GitHub Actions, usados como evidência técnica
  e não como canal de conversa com clientes.

Não encaminhe para canais públicos URLs de webhook, credenciais, tokens, dados
pessoais, conteúdo de mensagens ou endereços IP. Para correlacionar registros,
use o horário, a categoria do alerta e o identificador da requisição.

## Prioridade

| Nível | Situação | Ação inicial |
| --- | --- | --- |
| Crítico | API ou banco indisponível, suspeita de vazamento ou risco de perda de dados | Interromper mudanças, investigar imediatamente e avisar o proprietário principal |
| Alto | Login amplamente bloqueado, agenda ou financeiro sem funcionar, integração essencial falhando | Iniciar diagnóstico assim que o alerta chegar |
| Médio | Falha parcial de e-mail, IA ou integração com alternativa manual disponível | Registrar, aplicar contingência e corrigir no mesmo período operacional |
| Informativo | Teste seguro do canal de alertas | Confirmar recebimento; não abrir incidente real |

## Primeiros passos

1. Confirme se o alerta é real e anote horário, ambiente, categoria, evento,
   código HTTP, rota e identificador da requisição.
2. Consulte `/api/v1/health` e `/api/v1/health/database` e verifique a execução
   mais recente do monitor no GitHub Actions.
3. Consulte os logs do Render no mesmo intervalo, procurando pelo identificador
   da requisição. Nunca copie segredos ou dados pessoais para a ocorrência.
4. Evite publicar uma nova versão enquanto a causa ainda estiver desconhecida.
5. Se uma alteração recente estiver relacionada, prepare o rollback para a
   última versão saudável. Preserve o banco e confirme as migrações antes de
   reverter código que altere o esquema.

## Ações por categoria

### API ou banco

- Confirme o estado do serviço e do PostgreSQL no Render.
- Verifique expiração, suspensão, limites do plano, conexões e resolução do host.
- Não recrie nem exclua o banco durante o diagnóstico.
- Se houver risco para os dados, suspenda operações de escrita e use o procedimento
  documentado de backup e restauração em um banco isolado.

### Login

- Diferencie bloqueio temporário esperado de indisponibilidade geral.
- Confirme se a contagem regressiva e o desbloqueio automático funcionam.
- Não remova o limite de tentativas para contornar o incidente.
- Investigue volume anormal sem registrar senha, token ou endereço IP no canal.

### E-mail

- Verifique a configuração e o estado do provedor, domínio, remetente e limites.
- Não confirme contas nem redefina senhas manualmente sem validar a identidade.
- Oriente o usuário a aguardar a recuperação do envio; não envie links de acesso
  por canais não autorizados.

### IA

- Confirme disponibilidade, autenticação, limites e tempo de resposta do provedor.
- Mantenha disponíveis os fluxos manuais da agenda; a IA não deve bloquear a
  operação principal.
- Não envie dados de clientes em testes feitos diretamente no provedor.

### Integrações e webhooks

- Identifique o provedor e a rota pelo alerta, sem publicar o corpo da requisição.
- Confirme assinatura, credencial, limite e estado do provedor.
- Reprocesse somente operações idempotentes ou comprovadamente não concluídas,
  evitando agendamento, cobrança ou mensagem em duplicidade.

## Recuperação e encerramento

Considere o incidente recuperado somente quando:

1. os dois endpoints de saúde responderem corretamente;
2. o monitor automático concluir uma execução saudável;
3. o fluxo afetado funcionar em um teste controlado, sem usar dados reais quando
   dados fictícios forem suficientes;
4. não surgirem novos erros equivalentes nos logs durante a observação inicial;
5. a ocorrência registrar início, impacto, causa conhecida ou provável, ações,
   horário da recuperação e versão implantada.

Se o GitHub abriu a ocorrência automática, aguarde o monitor saudável comentar a
recuperação e encerrá-la. Para alertas apenas no Discord, registre um resumo no
canal privado e, quando houver correção de código ou risco de recorrência, abra
uma ocorrência técnica no GitHub sem dados sensíveis.

## Após o incidente

- Documente a causa raiz e uma ação preventiva proporcional ao impacto.
- Transforme correções reproduzíveis em testes automatizados.
- Revise limites, alertas e instruções que tenham atrasado o diagnóstico.
- Para incidentes críticos, valide backup e restauração antes de considerar o
  acompanhamento concluído.
