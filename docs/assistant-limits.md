# Limites do assistente por barbearia

O endpoint autenticado `POST /api/v1/businesses/{business_id}/assistant/messages`
reserva uma tentativa antes de construir o cliente do provedor de IA.

| Configuração | Padrão | Valores aceitos |
| --- | --- | --- |
| `ASSISTANT_REQUESTS_PER_MINUTE` | 20 | 1 a 1000 |
| `ASSISTANT_REQUESTS_PER_HOUR` | 200 | 1 a 10000 |

Proprietário principal e coproprietários compartilham os limites da empresa.
Outra barbearia tem contadores próprios. A autorização ocorre antes do consumo:
uma chamada sem login ou a tentativa de acessar outra empresa não reserva quota.
Sem chave de IA, a resposta continua HTTP 503, sem consumir tentativas.

## Persistência e resposta

A migração `5f6a7b8c9d0e` cria `assistant_usage_limits`, com uma linha por empresa.
O PostgreSQL bloqueia essa linha durante a decisão, serializando solicitações
concorrentes inclusive entre processos da API. Logout e reinício não apagam os
contadores. A linha acompanha a exclusão da empresa por chave estrangeira.

As janelas começam no primeiro uso e renovam ao completar 60 e 3600 segundos,
respectivamente. Elas não representam minuto ou hora de calendário. Quando uma
janela se esgota, a API retorna HTTP 429, texto em português e `Retry-After` em
segundos. Se ambas estiverem esgotadas, prevalece a maior espera. Solicitações
recusadas não incrementam contadores nem estendem a janela.

O contador é confirmado antes da lógica do assistente, na mesma sessão que até
esse ponto fez somente leituras de autenticação. Assim, erros do provedor ou
rollback posterior de um agendamento não devolvem a tentativa consumida. O
serviço de consumo não deve ser chamado depois de alterações de negócio pendentes.

A agenda manual não utiliza esse contador e continua disponível quando o limite
do assistente é atingido. Nenhum endereço IP, mensagem, telefone ou token é
armazenado na tabela de limites. O contador identifica a empresa internamente.

## Validação

Os testes locais verificam as bordas das janelas, a prioridade da maior espera,
configurações inválidas e a resposta 429 antes da construção do cliente de IA.

O cenário `tests/integration/test_assistant_usage_database.py` usa PostgreSQL
real, duas empresas e três sessões autenticadas, com somente o modelo externo
simulado. Verifica quatro chamadas concorrentes, quota compartilhada com o
coproprietário, persistência após erro do provedor, isolamento entre empresas,
renovação automática e consulta da agenda manual enquanto a IA está limitada.

Execute com Docker aberto:

```powershell
.\.venv-codex\Scripts\python.exe .\scripts\test_tenant_isolation.py
```

Em 28/10/2026, André apresentou a execução em PostgreSQL temporário: oito testes
aprovados e um pulado em 29,31 segundos. O cenário de limites passou, incluindo
concorrência, espera, renovação e isolamento; o teste pulado foi o de carga,
executado separadamente com `--load`. Todas as migrações foram aplicadas, incluindo
`5f6a7b8c9d0e`. O contêiner foi removido sem criação de volumes.

A suíte local também passou com 361 testes; lint, formatação, tipos e geração
offline do SQL foram conferidos. A aprovação no CI e a publicação ainda estão
pendentes. Nenhuma chave real foi necessária e o modelo externo foi simulado.

## Escopo

Os limites contam mensagens recebidas, não tokens nem reais gastos. Uma mensagem
pode gerar mais de uma chamada ao provedor. Orçamento e alertas de faturamento
continuam sendo configurações separadas. Estes limites não substituem controles
dos endpoints públicos, login ou proteção contra ataques de rede.
