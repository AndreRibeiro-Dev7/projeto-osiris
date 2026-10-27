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
- [ ] Criar uma versão identificável e documentar como fazer rollback.

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
- [ ] Desativar `DEBUG` e restringir a documentação da API em produção.
- [ ] Aplicar limites de requisição em login, IA e endpoints públicos.
- [x] Revisar autorização e isolamento dos dados de cada empresa.
- [ ] Criar trilha de auditoria para ações administrativas e financeiras.
- [ ] Definir política de privacidade, retenção e exclusão de dados (LGPD).
- [ ] Revisar dependências e corrigir vulnerabilidades conhecidas.

## 4. E-mail e integrações

- [ ] Verificar um domínio de envio no Resend.
- [ ] Validar confirmação de e-mail e recuperação de senha.
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
- [ ] Testar agenda, conflitos, folgas, cancelamento e reagendamento.
- [x] Testar o fluxo HTTP de agendamento público com PostgreSQL real.
- [x] Testar a orquestração do assistente com PostgreSQL real e modelo simulado.
- [ ] Testar interpretação e respostas do assistente com o provedor real de IA.
- [x] Testar pagamentos, comissões, despesas, metas e relatórios em homologação isolada.
  Cenário HTTP aprovado com PostgreSQL em 27/10/2026, conforme o
  [guia de validação financeira](./financial-validation.md). A revisão visual da
  versão implantada permanece pendente.
- [ ] Testar interface em celular, tablet e computador.
- [x] Testar isolamento com duas empresas diferentes.
- [ ] Realizar teste de carga compatível com o uso esperado.
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
