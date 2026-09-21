# Checklist para produção

Este documento reúne as condições recomendadas para transformar o MVP do
Projeto Osiris em uma aplicação segura para uma barbearia real. Um item só deve
ser marcado quando tiver sido executado e validado no ambiente de produção.

## 1. Preparação da versão

- [ ] Revisar alterações pendentes e remover arquivos temporários.
- [ ] Confirmar que nenhuma chave, senha ou dado pessoal está versionado.
- [ ] Executar testes, lint, formatação e verificação de tipos.
- [ ] Aplicar todas as migrações em um banco de homologação.
- [ ] Criar uma versão identificável e documentar como fazer rollback.

## 2. Infraestrutura

- [ ] Publicar a API em um serviço com reinício automático e health check.
- [ ] Configurar domínio próprio e HTTPS obrigatório.
- [ ] Usar PostgreSQL gerenciado, sem acesso público desnecessário.
- [ ] Separar as configurações de desenvolvimento, homologação e produção.
- [ ] Armazenar segredos no serviço de hospedagem, nunca no repositório.
- [ ] Configurar backup automático e testar uma restauração completa.

## 3. Segurança e proteção de dados

- [ ] Gerar uma chave JWT exclusiva e forte para produção.
- [ ] Desativar `DEBUG` e restringir a documentação da API em produção.
- [ ] Aplicar limites de requisição em login, IA e endpoints públicos.
- [ ] Revisar autorização e isolamento dos dados de cada empresa.
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

- [ ] Centralizar logs sem registrar senhas, tokens ou dados sensíveis.
- [ ] Monitorar disponibilidade, latência, erros e conexões com o banco.
- [ ] Criar alertas para falhas de login, e-mail, IA e integrações.
- [ ] Registrar métricas de agendamento e tarefas financeiras críticas.
- [ ] Documentar procedimento de incidente e canais de suporte.

## 6. Testes antes do lançamento

- [ ] Testar cadastro, login, logout e recuperação de acesso.
- [ ] Testar agenda, conflitos, folgas, cancelamento e reagendamento.
- [ ] Testar agendamento público e fluxo completo do assistente.
- [ ] Testar pagamentos, comissões, despesas, metas e relatórios.
- [ ] Testar interface em celular, tablet e computador.
- [ ] Testar isolamento com duas empresas diferentes.
- [ ] Realizar teste de carga compatível com o uso esperado.
- [ ] Fazer homologação com dados fictícios e depois com o cliente piloto.

## 7. Entrada em operação

- [ ] Cadastrar dados reais da primeira barbearia e seus profissionais.
- [ ] Treinar o proprietário nos fluxos essenciais e de contingência.
- [ ] Definir responsável por suporte, backup e faturamento dos serviços.
- [ ] Acompanhar os primeiros dias com alertas e revisão diária dos erros.
- [ ] Registrar feedback e priorizar correções antes de aceitar novos clientes.

## Critério de conclusão

O Osiris pode ser considerado pronto para operação comercial quando os itens
críticos de infraestrutura, segurança, backup, acesso, agenda e pagamentos
estiverem validados em produção e a primeira barbearia concluir uma semana de
uso acompanhado sem perda de dados ou bloqueio operacional.
