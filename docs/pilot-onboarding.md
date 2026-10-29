# Preparação da barbearia piloto

Situação em 29/10/2026: nenhuma barbearia piloto foi escolhida. Este roteiro
prepara a demonstração e a futura operação acompanhada; não registra aprovação
de uso real. A compra do domínio está planejada por André para 02/11/2026.

## Etapas e responsáveis

| Etapa | Responsável | Evidência para concluir |
| --- | --- | --- |
| Escolher a barbearia | André | Estabelecimento e responsável confirmados |
| Levantar os dados | André e proprietário | Ficha de implantação preenchida |
| Ensaiar com dados fictícios | André | Roteiro abaixo executado e resultados registrados |
| Preparar a empresa e os acessos | Operador do Osiris | Empresa separada da demonstração, conta principal e papéis conferidos |
| Conferir ambiente e integrações | Operador do Osiris | Checklist de produção e recursos liberados registrados |
| Treinar e iniciar | André e proprietário | Primeiro atendimento acompanhado e canais de suporte definidos |
| Acompanhar sete dias de operação | André e proprietário | Agenda e financeiro reconciliados; problemas registrados |

## Ficha de implantação

Preencha os dados reais em uma cópia local na pasta ignorada `work/`, fora do Git.
A ficha deve conter os itens abaixo; não inclui senhas nem tokens.

- Nome e telefone da barbearia, cidade e fuso horário confirmado.
- Nome do responsável e e-mail da conta principal.
- Profissionais: nome, telefone, comissão percentual e necessidade de login.
- Serviços: nome, duração em minutos e preço em reais.
- Jornada de cada profissional por dia, intervalo de início dos horários e pausa.
- Folgas previstas e dias de fechamento do estabelecimento.
- Coproprietários necessários e quem poderá administrar os acessos.
- Meta mensal, despesas fixas iniciais e decisão sobre fidelidade.
- Aparelhos usados pelo dono e pelos profissionais.
- Data de início, responsável pelo suporte e canal de contato.
- Recursos incluídos no piloto: agenda, financeiro, reserva pública e integrações.

Confirme serviços, preços, comissões e jornadas com o proprietário antes de
divulgar o link de agendamento. A comissão atual do profissional é usada nos
relatórios; mudanças durante o piloto exigem reconferência dos resultados.

## Ensaio de demonstração

Use uma instalação de demonstração ou homologação identificada e dados fictícios.
O histórico simulado de 2025–2027 não representa uma barbearia real. Não transforme
essa empresa em cliente apenas renomeando-a, nem apague o histórico para fazer o ensaio.
O cadastro de uma empresa separada e sua conta inicial é uma etapa do operador,
conforme o [guia de publicação](./deployment.md#publicação-inicial-no-render).
O bootstrap fica desativado após criar a conta principal.

Exemplo de catálogo exclusivamente para demonstração:

| Cadastro | Configuração fictícia |
| --- | --- |
| Empresa | Osiris — Demonstração do piloto |
| Fuso | America/Sao_Paulo, somente se corresponder ao cenário escolhido |
| Profissional A | Comissão de 50% |
| Profissional B | Comissão de 50% |
| Corte de demonstração | 30 minutos, R$ 50,00 |
| Barba de demonstração | 30 minutos, R$ 30,00 |
| Jornada de teste | Segunda a sexta, 09:00–18:00, pausa 12:00–13:00 |
| Contatos | Dados fictícios no ambiente isolado; canais controlados se houver teste de entrega |

Escolha uma data futura com jornada configurada para testar a reserva pública.
Nenhuma mensagem externa deve ser enviada durante o ensaio básico.

| Passo | Onde conferir | Resultado esperado |
| --- | --- | --- |
| Entrar e sair como dono | Painel do proprietário | Dados da empresa correta; saída retorna ao login |
| Criar acesso profissional | Equipe | Conta vinculada ao profissional; indicação de acesso já criado |
| Entrar como profissional | Painel do barbeiro | Apenas sua agenda e ações permitidas; sem financeiro ou gestão de contas |
| Conferir catálogo e jornada | Serviços e Equipe | Preços, duração, pausas e dias de trabalho combinados |
| Abrir link público no celular | Agendamento online | Serviço e profissional corretos; nenhum horário passado |
| Reservar e conferir no painel | Página do cliente e Agenda | Uma única reserva, mesmo profissional e horário nos dois lados |
| Tentar o mesmo horário | Outro navegador | Horário indisponível ou conflito; sem segunda reserva |
| Reagendar e cancelar | Meus agendamentos | Alteração refletida na agenda e liberação do horário cancelado |
| Concluir dois atendimentos de teste | Agenda | Uma conclusão por atendimento; forma de pagamento registrada |
| Registrar despesa de teste | Financeiro | Valor e período conferidos, sem duplicidade ao confirmar pagamento |
| Conferir autoria e filtro | Atividades | Ações e autores coerentes, sem edição ou exclusão das entradas |
| Sair e entrar novamente | Ambos os painéis | Dados persistidos e permissões preservadas |

Os dois atendimentos concluídos e a despesa devem pertencer ao mesmo período do
relatório. Em um período vazio, sem outros lançamentos, um corte de R$ 50,00 e
uma barba de R$ 30,00, ambos com comissão de 50%, e uma despesa de R$ 20,00 devem
produzir: faturamento R$ 80,00, comissões R$ 40,00, líquido após comissões
R$ 40,00 e resultado após despesas R$ 20,00. Confira também a exportação Excel.
Os pagamentos são registros de teste; não é necessário transferir dinheiro.
O [critério do relatório](./financial-validation.md) inclui despesas do período,
mesmo pendentes, e não equivale a um extrato bancário.

## Condições antes do uso real

- Revisar o [checklist de produção](./production-checklist.md), segredos,
  `DEBUG=false`, acesso ao banco, suporte, capacidade e recuperação dos dados.
- Confirmar um backup recente e o procedimento de recuperação. A restauração
  aprovada da cópia de setembro não confirma atualização para migrações novas.
- Definir os avisos e procedimentos de privacidade, retenção e exclusão.
- Conferir a agenda, o financeiro e as permissões nos aparelhos usados no piloto.
- Informar quais canais de recuperação de acesso estão disponíveis ao usuário.
  O remetente de teste do Resend não comprova entrega aos demais usuários.
  Antes de liberar recuperação por e-mail, verificar o domínio e testar a entrega.
- Manter WhatsApp e IA fora do escopo liberado enquanto os respectivos fluxos
  reais, entregas e limites de consumo não estiverem validados. O piloto básico
  pode usar a reserva pública e o gerenciamento no mesmo navegador.

No fluxo sem WhatsApp, a recuperação de reservas em outro aparelho ainda não está
liberada. O cliente deve poder solicitar auxílio ao estabelecimento, que localiza
o atendimento no painel pelo procedimento combinado, sem divulgar links de acesso.

## Semana acompanhada

| Momento | Conferência |
| --- | --- |
| Antes da abertura | API e banco saudáveis; profissionais e horários corretos |
| Ao longo do dia | Novas reservas aparecem; cancelamentos e reagendamentos conferidos |
| Ao fechar o dia | Atendimentos e formas de pagamento conferidos com o responsável |
| Diariamente | Despesas, comissões, erros, alertas e pedidos de suporte revisados |
| Após sete dias de operação | Revisão com o dono; corrigir pendências antes de ampliar o uso |

Registre cada problema com data, aparelho, ação e resultado esperado, sem senha,
token ou captura com dados de clientes. Para cada cenário, registre pendente,
aprovado ou reprovado, responsável e evidência. Um erro com perda de dados, acesso
indevido, dupla reserva ou valor incorreto deve ser investigado antes de expandir
o uso. A contingência e o suporte seguem o [procedimento de incidentes](./incident-response.md).

Nenhuma etapa deste roteiro foi executada em nome de uma barbearia real.
