# Checklist para produção

Este documento reúne as condições recomendadas para transformar o MVP do
Projeto Osiris em uma aplicação segura para uma barbearia real. Um item só deve
ser marcado com evidência de execução no ambiente correspondente: os testes e as
migrações preparatórias em homologação; a infraestrutura e as configurações
operacionais em produção. A aprovação em homologação não substitui a validação
da versão implantada.

## 1. Preparação da versão

- [ ] Revisar alterações pendentes e remover arquivos temporários.
- [ ] Confirmar que nenhuma chave, senha ou dado pessoal está versionado.
- [x] Executar testes, lint, formatação e verificação de tipos.
- [x] Aplicar todas as migrações em um banco de homologação.
- [x] Criar uma versão identificável e documentar como fazer rollback.
  A identificação em `/api/v1/health` foi conferida na versão publicada, e o
  procedimento está no [guia de publicação](./deployment.md#atualizações-e-rollback).
  Nenhum rollback de produção foi executado.

## 2. Infraestrutura

- [x] Publicar a API em um serviço com reinício automático e health check.
- [ ] Configurar domínio próprio e HTTPS obrigatório.
- [ ] Usar PostgreSQL gerenciado, sem acesso público desnecessário.
- [ ] Separar as configurações de desenvolvimento, homologação e produção.
- [ ] Armazenar segredos no serviço de hospedagem, nunca no repositório.
- [x] Confirmar backup contínuo e recuperação ponto a ponto do Render Postgres pago.
- [x] Testar uma restauração completa em banco vazio e isolado.

## 3. Segurança e proteção de dados

- [ ] Gerar uma chave JWT exclusiva e forte para produção.
- [ ] Conferir `DEBUG=false` nas variáveis efetivas do serviço de produção.
- [x] Restringir a documentação da API em produção.
  Swagger, ReDoc e OpenAPI retornaram HTTP 404 no commit `e63b845`, conforme a
  [revisão HTTP](./browser-security.md). API e painel incluíram os cabeçalhos esperados.
- [ ] Aplicar limites de requisição em login, IA e endpoints públicos.
  Os [limites persistentes do assistente](./assistant-limits.md) foram aprovados
  em PostgreSQL temporário, com HTTP 429 e espera informada. André apresentou
  oito testes aprovados em 29,31 segundos. A publicação está pendente. O item continua aberto para os
  demais endpoints e sua validação em produção.
- [x] Revisar autorização e isolamento dos dados de cada empresa.
- [ ] Criar trilha de auditoria para ações administrativas e financeiras.
- [ ] Definir política de privacidade, retenção e exclusão de dados (LGPD).
- [x] Revisar dependências e corrigir vulnerabilidades conhecidas no inventário local.
  A [auditoria das dependências](./dependency-security.md) identificou avisos em
  ferramentas de desenvolvimento, que foram atualizadas. A nova consulta dos
  92 pacotes locais não encontrou avisos conhecidos. O novo job foi aprovado no
  CI do commit `e63b845`; a imagem de produção não foi inventariada.

## 4. E-mail e integrações

- [ ] Verificar um domínio de envio no Resend.
- [x] Validar recuperação por e-mail com remetente de teste, no e-mail da própria conta Resend.
  Fluxo manual confirmado por André em 27/10/2026, conforme o
  [guia de autenticação](./authentication.md#teste-manual-de-entrega-do-resend).
- [ ] Validar confirmação de troca de e-mail e entrega aos demais usuários com domínio verificado.
- [ ] Configurar a API oficial do WhatsApp e seus webhooks.
- [ ] Concluir sincronização e tratamento de erros do calendário.
- [ ] Definir limites e alertas de consumo para OpenAI e demais provedores.

## 5. Observabilidade

- [x] Centralizar logs sem registrar senhas, tokens ou dados sensíveis.
- [x] Configurar monitor automático da API, banco e alerta ao proprietário.
- [x] Validar as primeiras execuções agendadas e saudáveis em produção.
- [x] Validar abertura e recuperação do alerta com uma falha controlada.
- [x] Monitorar disponibilidade, latência, erros e conexões com o banco.
- [x] Criar alertas para falhas de login, e-mail, IA e integrações.
- [x] Registrar métricas de agendamento e tarefas financeiras críticas.
- [x] Documentar procedimento de incidente e canais de suporte.

## 6. Testes antes do lançamento

- [ ] Testar cadastro, login, logout e recuperação de acesso.
  Testes específicos de login, bloqueio e recuperação preparados no
  [guia de autenticação](./authentication.md#validação-adicional-de-acesso-em-27102026);
  a homologação PostgreSQL foi aprovada em 27/10/2026. A entrega real de e-mail
  e a conferência dos demais fluxos de cadastro e logout permanecem pendentes.
- [x] Testar agenda, conflitos, folgas, cancelamento e reagendamento em homologação isolada.
  O cenário HTTP da agenda interna está documentado no
  [guia de agendamento](./scheduling.md#validação-adicional-da-agenda-interna),
  incluindo concorrência e fechamento. André apresentou sete testes de integração
  aprovados em PostgreSQL temporário (12,80 segundos). Falta conferir a publicação
  da correção; pausas e folgas foram verificadas na disponibilidade calculada.
- [x] Testar o fluxo HTTP de agendamento público com PostgreSQL real.
- [x] Testar a orquestração do assistente com PostgreSQL real e modelo simulado.
- [ ] Testar interpretação e respostas do assistente com o provedor real de IA.
- [x] Testar pagamentos, comissões, despesas, metas e relatórios em homologação isolada.
  Cenário HTTP aprovado com PostgreSQL em 27/10/2026, conforme o
  [guia de validação financeira](./financial-validation.md). A revisão visual da
  versão implantada permanece pendente.
- [ ] Testar interface em celular, tablet e computador.
  A cobertura inclui reserva pública, login e painéis do proprietário e barbeiro,
  conforme o [guia de interface](./interface-validation.md). A agenda e o financeiro
  publicados e o painel restrito do profissional no celular foram conferidos
  pelo usuário. A revisão nos demais aparelhos e em Safari/iOS permanece pendente.
- [x] Testar isolamento com duas empresas diferentes.
- [ ] Realizar teste de carga compatível com o uso esperado.
  O [cenário moderado e isolado](./load-validation.md) foi executado por André:
  100 consultas bem-sucedidas com concorrência de dez requisições, p95 de 309,7 ms
  e uma única reserva em dez tentativas simultâneas, sem cadastros órfãos.
  Falta o ensaio com infraestrutura e histórico comparáveis ao uso esperado;
  o resultado local não mede a capacidade do plano de produção.
- [ ] Fazer homologação com dados fictícios e depois com o cliente piloto.

## 7. Entrada em operação

- [ ] Cadastrar dados reais da primeira barbearia e seus profissionais.
- [ ] Treinar o proprietário nos fluxos essenciais e de contingência.
- [ ] Definir responsável por suporte, backup e faturamento dos serviços.
- [ ] Acompanhar os primeiros dias com alertas e revisão diária dos erros.
- [ ] Registrar feedback e priorizar correções antes de aceitar novos clientes.

## Critério de conclusão

A evidência da revisão de autorização, das migrações e do teste com duas empresas
está no [guia de autenticação](./authentication.md#resultado-da-homologação).

Em 26 de outubro de 2026, após corrigir as pendências do job `quality`, foram
aprovados localmente `ruff check .`, `black --check .`, `mypy app` (88 arquivos)
e a suíte com 297 testes. O teste PostgreSQL optativo foi pulado nessa execução;
sua homologação isolada está documentada no guia de autenticação. A aprovação
do novo commit no GitHub Actions ainda deve ser conferida após a publicação.

O Osiris pode ser considerado pronto para operação comercial quando os itens
críticos de infraestrutura, segurança, backup, acesso, agenda e pagamentos
estiverem validados em produção e a primeira barbearia concluir uma semana de
uso acompanhado sem perda de dados ou bloqueio operacional.
