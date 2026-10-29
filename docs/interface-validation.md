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

## Painel do barbeiro

O teste `scripts/test_barber_ui.cjs` verifica larguras de 375, 768 e 1280 pixels.
Confere a agenda exclusiva do profissional, ausência dos controles administrativos,
detalhes do cliente e serviço e observações em modo somente leitura. Exercita
confirmação, conclusão com Pix, falha de pagamento com nova tentativa, falta,
sessão expirada e saída da conta. Todas as chamadas são interceptadas: nenhum
pagamento, mensagem ou atendimento real é alterado. O teste também verifica que
as chamadas da interface usam as rotas próprias do barbeiro; a autorização do
servidor continua coberta pelos testes de integração separados.

As observações agora ficam somente para leitura no painel do profissional,
coerente com a ausência de permissão para salvá-las.

Os **11 testes de navegador passaram localmente** em 27/10/2026: dois da reserva,
dois do login, quatro do proprietário e três do barbeiro. Os dois testes Python
de configuração de deploy e monitoramento também passaram.

## Histórico dos resultados

### Atividades em 29/10/2026

Os quatro cenários do proprietário passaram com histórico preenchido, em 375,
768 e 1280 pixels e no tablet com fonte alternativa. Conferem filtro por área,
resultado vazio, autoria de proprietário principal, coproprietário excluído e
profissional, além do horário no fuso da barbearia. Textos contendo HTML são
exibidos como texto, sem criar imagens ou scripts executáveis. Não há botões
de edição ou exclusão nas entradas.

Foi corrigida a atualização que mantinha entradas antigas na tela após falha
de leitura: agora a lista mostra aviso e orienta usar Atualizar. O teste simula
HTTP 503, verifica a remoção dos dados anteriores e uma nova tentativa bem-sucedida.
O endereço versionado de `app.js` foi atualizado para renovar o cache.

Os outros sete cenários de reserva, login e barbeiro também passaram: 11 testes
de navegador aprovados. Os dois testes Python de configuração passaram; cinco
cenários Bash/Linux ficaram ignorados no Windows. Ruff, Black e a conferência
de espaços do diff passaram. A API é simulada nessa validação, sem mutações reais.
A melhoria foi publicada no commit `35371ae`, com quatro jobs do
[GitHub Actions](https://github.com/AndreRibeiro-Dev7/projeto-osiris/actions/runs/40930803601)
aprovados. A revisão, a referência versionada de `app.js` e a mensagem de falha
foram conferidas no Render, com API e banco saudáveis. A conferência manual
autenticada de Atividades em produção permanece separada dos testes simulados.

Os sete testes iniciais passaram localmente, mas o CI do commit `9bc3fbd`
detectou 13 pixels de transbordamento nos indicadores financeiros do tablet.
Qualidade e PostgreSQL passaram nessa execução; somente a interface falhou.
O problema foi reproduzido localmente ao aplicar Arial também aos títulos e
reservar o espaço da barra de rolagem, como cenário de fonte alternativa.

A correção permite que os cartões de indicadores reduzam a largura mínima e
quebrem conteúdo quando necessário, sem esconder o excesso na página. O cenário
foi mantido como regressão. Os **oito testes de navegador passaram** após corrigir:
dois da reserva, dois do login e quatro do painel do proprietário. Os testes Python
de dependências de deploy e workflow também passaram. O GitHub Actions executa
os quatro scripts e guarda capturas das falhas de largura dos painéis como artefato.

O commit `7f3a359` foi aprovado no GitHub Actions, publicado no Render e teve a
agenda e o financeiro conferidos pelo usuário. A ampliação para o painel do
barbeiro foi aprovada no CI do commit `2dd9f01`; André também confirmou a
publicação e a revisão do painel no celular.
Esta validação usa Chromium e não substitui testes em aparelhos reais ou Safari/iOS.
