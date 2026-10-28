# Validação da interface

Em 27/10/2026, foram executados testes de navegador com os arquivos reais de `dist`
e respostas de API simuladas, sem usar contas reais ou modificar produção.

## Painel do proprietário

O teste `scripts/test_owner_ui.cjs` percorre visão geral, agenda, clientes, equipe,
serviços, financeiro, agendamento online, configurações, coproprietários,
atividades e fechamentos. Também abre e fecha os formulários de agendamento,
despesa e cliente e a janela de segurança da conta.

Foram usadas larguras de 375, 768 e 1280 pixels, com nomes longos de empresa,
profissional, cliente e e-mail. A verificação detectou e motivou as correções:

- Cabeçalho com altura flexível, sem cortar nome e data.
- Ações dos atendimentos e despesas com quebra de linha, evitando transbordamento.
- Formulário de meta e controles financeiros adaptados ao espaço restante ao lado
  do menu no tablet.
- Cartões de coproprietários capazes de ocupar uma coluna estreita.
- Menu fechado ao sair da conta, evitando que fique aberto na próxima entrada.

O teste verifica que as páginas e janelas cabem na largura da tela. Em celular,
reduz a altura para 480 pixels e verifica rolagem própria do menu, acesso ao último
item e botão de sair visível. O logout é acionado pela interface e a remoção do
token local é conferida. As requisições desse cenário são restritas a leitura.

## Reserva pública e login

Os cenários anteriores de reserva e login continuam sendo executados em celular
e computador, incluindo cancelamento, horário expirado, recuperação por WhatsApp
simulada, contador de bloqueio e recuperação de senha simulada.

## Resultado e limites

Os **sete testes de navegador passaram**: dois da reserva, dois do login e três
do painel do proprietário. Os testes Python de dependências de deploy e workflow
também passaram. O GitHub Actions passa a executar os três scripts de navegador.

Ainda faltam a aprovação desse commit no CI, a publicação e a revisão visual da
versão implantada. Esta validação usa Chromium: não substitui teste em aparelhos
reais, Safari/iOS ou a revisão específica do painel restrito do profissional.
