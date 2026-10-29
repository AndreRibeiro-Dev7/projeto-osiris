# Teto de criação de reservas públicas

O endpoint `POST /api/v1/public/businesses/{business_id}/appointments` passa a
limitar as tentativas por barbearia, antes de criar cliente ou agendamento.

| Variável | Padrão | Valores aceitos |
| --- | --- | --- |
| `PUBLIC_BOOKING_REQUESTS_PER_MINUTE` | 20 | 1 a 1000 |
| `PUBLIC_BOOKING_REQUESTS_PER_HOUR` | 200 | 1 a 10000 |

É um orçamento agregado: visitantes da mesma barbearia compartilham os contadores,
mesmo usando profissionais ou redes diferentes. Uma pessoa pode esgotar esse teto
para os demais visitantes até a renovação. Os valores devem ser ajustados ao
movimento observado. A agenda interna permanece como alternativa para a equipe.

## Decisão sobre IP e cabeçalhos

O Render descreve uma cadeia com Cloudflare e balanceadores e orienta a consulta
de `X-Forwarded-For` na sua
[documentação sobre proteção de tráfego](https://render.com/articles/how-render-handles-ddos-attacks).
Essa referência não estabelece, por si só, a lista de proxies que esta aplicação
deve confiar. Antes de adotar um bloqueio individual por IP, a cadeia efetiva deve
ser validada conforme os cuidados descritos na
[referência do cabeçalho](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Forwarded-For).

Nesta etapa foi escolhido o teto por empresa, que independe do IP, de cookies ou
de cabeçalhos fornecidos pelo visitante. Não foram alteradas as configurações de
proxy do Uvicorn nem a identificação de IP usada em outros fluxos. Esta mudança
não deve ser apresentada como uma validação dessas configurações.

## Funcionamento

A migração `6a7b8c9d0e1f` adiciona `public_booking_usage_limits`, com uma linha por
empresa. Não armazena IP, telefone, nome ou token do visitante. O limite da IA
continua em tabela própria, com contadores independentes. Os dois fluxos usam a
mesma lógica de controle de janelas e bloqueio transacional no PostgreSQL.

A empresa precisa existir antes de reservar quota. Payloads inválidos rejeitados
pelo schema não consomem tentativas. Os demais pedidos admitidos consomem uma
tentativa antes da criação, inclusive quando depois há conflito de horário ou
outra recusa de negócio. O rollback da reserva não devolve essa tentativa.

As janelas duram 60 e 3600 segundos a partir do primeiro uso. Quando se esgotam,
a API retorna HTTP 429, texto em português e `Retry-After` em segundos. A resposta
não cria cliente ou reserva. Negativas de quota não incrementam nem prolongam os
contadores. Reiniciar o serviço não elimina o controle.

Consultar a barbearia, listar horários, confirmar, cancelar e reagendar reservas
existentes não usa esse novo contador. Esses endpoints continuam exigindo suas
validações e tokens próprios; limites específicos para eles ainda são uma pendência.

## Evidências e execução

Os testes locais de API verificam HTTP 429 antes de qualquer criação, resposta de
empresa inexistente e configurações inválidas. A suíte passou com 367 testes e
15 cenários pulados por dependerem de Linux ou PostgreSQL. Lint, formatação,
tipos e geração offline do SQL também foram conferidos.

Os testes de navegador em 375 e 1280 pixels simulam a recusa, conferem o texto de
espera e a preservação do nome e telefone no formulário e concluem uma nova
tentativa. A consulta de horários continua funcionando após o erro.

O teste adicional `tests/integration/test_public_booking_usage_database.py`
verifica concorrência, troca de cabeçalhos, isolamento entre
empresas, renovação, persistência após conflito e gestão de reservas durante o
bloqueio. Execute em PostgreSQL temporário com Docker aberto:

```powershell
& ".\.venv-codex\Scripts\python.exe" ".\scripts\test_tenant_isolation.py"
```

Em 29/10/2026, André apresentou a execução em PostgreSQL temporário: nove testes
aprovados e um pulado em 22,85 segundos. A migração `6a7b8c9d0e1f` foi aplicada,
os limites públicos e de IA passaram, e o contêiner foi removido sem volumes.
O teste pulado foi o de carga, executado separadamente com `--load`.

A aprovação no CI e a publicação ainda estão pendentes. Não foi feito teste de
excesso de tráfego em produção e nenhum agendamento real foi alterado.
