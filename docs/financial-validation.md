# Validação do financeiro

## Cálculos consistentes

O relatório usa centavos inteiros. A comissão é calculada por atendimento concluído,
descartando a fração inferior a um centavo, e os valores individuais são somados nos
totais por profissional, cartões, resultados diários e exportação Excel.

Antes desta correção, o gráfico arredondava por atendimento e o total arredondava
o faturamento acumulado do profissional. Dois atendimentos de R$ 10,01 com comissão
de 50% produziam R$ 10,00 de comissão no gráfico e R$ 10,01 no total. Agora ambos
usam R$ 10,00. A porcentagem utilizada continua sendo a configuração atual do
profissional; esta alteração não adiciona histórico de porcentagens.

O preço do atendimento permanece o registrado na reserva, mesmo após alterar o
preço do catálogo. Apenas atendimentos concluídos entram no faturamento. Despesas
pagas e pendentes entram no resultado do período pela data do lançamento; o estado
de pagamento não muda esse critério. O relatório não é um extrato bancário.

## Geração de despesas fixas

A geração bloqueia a linha da barbearia até concluir a transação. Duas requisições
simultâneas para gerar o mesmo mês são processadas em sequência, sem duplicar as
cópias da geração. O mês de destino é normalizado para o primeiro dia e vencimentos
inexistentes são limitados ao último dia: 31 de janeiro vira 28 de fevereiro de 2030.
As novas despesas começam pendentes. Repetir a geração não cria novas cópias.

## Testes

`tests/test_financial_report.py` reproduz a diferença de arredondamento e verifica
reconciliação dos totais, estados dos atendimentos, formas de pagamento, dias no
fuso da barbearia e um período sem movimentação. Em 27/10/2026, esses testes e a
suíte Python local passaram: **331 aprovados**, com **5 integrações PostgreSQL
puladas**. Ruff, Black e mypy também passaram.

`tests/integration/test_financial_database.py` usa duas barbearias fictícias,
PostgreSQL temporário, autenticação e requisições HTTP reais à aplicação para validar:

- Pagamento por Pix e dinheiro e preservação do preço da reserva.
- Conclusão repetida e concorrente de atendimento, sem faturamento duplicado.
- Exclusão de cancelamentos, faltas e reservas ativas do faturamento.
- Criação, pagamento, reabertura, edição e exclusão de despesas.
- Totais do relatório e do Excel, incluindo comissão e resultado final.
- Geração sequencial e concorrente de despesas fixas em fevereiro.
- Persistência da meta mensal e recusa de intervalos de data inválidos.
- Impedimento de leitura financeira de outra barbearia.

A homologação PostgreSQL deste novo cenário está pendente. Execute o mesmo
`scripts/test_tenant_isolation.py` usado nas homologações anteriores; ele aplica
migrações e executa todas as integrações sem utilizar o banco de produção.
O cenário financeiro não envia mensagens nem realiza cobranças externas.
