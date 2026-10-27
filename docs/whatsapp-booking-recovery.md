# Consultar reservas por WhatsApp

O recurso complementa **Meus agendamentos** para quem mudou de navegador ou aparelho.
Ele permanece desativado por padrão. O agendamento e a lista local continuam
funcionando sem WhatsApp.

## Preparação na Meta

1. No [Meta for Developers](https://developers.facebook.com/apps/), configure um app
   com acesso à WhatsApp Business Platform e um número de envio habilitado.
2. No WhatsApp Manager da conta, crie e obtenha aprovação de um modelo de categoria
   **AUTHENTICATION**, idioma **Português (Brasil)**, chamado `osiris_booking_access`.
   Use botão de copiar código e validade de **5 minutos**. Não use modelo de marketing
   nem uma mensagem de texto livre para enviar o código.
3. Obtenha o **Phone Number ID** do número remetente, a versão suportada da Graph API
   e um token de produção com permissão `whatsapp_business_messaging`. O ID não é o
   número de telefone nem o ID da conta empresarial. Tokens temporários de teste
   servem apenas para homologação com destinatários permitidos pela Meta.
4. Antes de ativar para clientes, valide o modelo aprovado com um destinatário de
   teste autorizado e confira a chegada no WhatsApp. Aceitação HTTP da Meta não
   confirma entrega; a verificação só funciona após o cliente receber o código.

Referência do fornecedor: [modelo de autenticação com botão de copiar código,
coleção oficial da Meta](https://www.postman.com/meta/whatsapp-business-platform/request/qzriq9r/create-authentication-template-w-otp-copy-code-button).

## Configuração do Osiris

No Render, serviço **osiris-api → Environment**, configure os valores abaixo como
variáveis do servidor. Não coloque o token no GitHub, no HTML ou em mensagens.

| Variável | Valor |
| --- | --- |
| `WHATSAPP_RECOVERY_ENABLED` | `false` durante preparação; `true` após homologar |
| `WHATSAPP_ACCESS_TOKEN` | Token de envio da Meta |
| `WHATSAPP_PHONE_NUMBER_ID` | ID do número remetente |
| `WHATSAPP_API_VERSION` | Versão suportada no app da Meta, no formato `vNN.0` |
| `WHATSAPP_AUTH_TEMPLATE` | Nome aprovado, padrão `osiris_booking_access` |
| `WHATSAPP_TEMPLATE_LANGUAGE` | Idioma aprovado, padrão `pt_BR` |
| `JWT_SECRET_KEY` | Segredo existente, exclusivo, com pelo menos 32 caracteres |

Não substitua o segredo JWT existente apenas para ativar este recurso: a rotação
invalida sessões e códigos pendentes. O envio usa um remetente do Osiris; a busca
das reservas permanece restrita à barbearia da página. Configurar um remetente
individual para cada barbearia é uma implementação futura.

A migração `4e5f6a7b8c9d` cria desafios e contadores persistentes de tentativas.
O deploy existente executa `alembic upgrade head`. Para desligar o recurso, basta
definir `WHATSAPP_RECOVERY_ENABLED=false`; não remova tabelas nem reservas.

## Fluxo e proteção de acesso

- O cliente informa o celular brasileiro com DDD e autoriza o envio de um código.
- São aceitos 11 dígitos locais ou 13 com DDI `55`; a formatação é removida. Outros
  países e números de telefone fixo não fazem parte desta versão.
- A solicitação envia um código mesmo que não existam reservas, sem revelar a
  existência de clientes na resposta. Nenhuma reserva aparece antes da verificação.
- O código tem seis dígitos, expira em cinco minutos e pode ser usado uma vez.
  São permitidos cinco erros por código, reenvio após 60 segundos e cinco envios
  por número/barbearia por hora. Reenviar invalida o código anterior.
- Há limites persistentes de dez solicitações por IP em 15 minutos, trinta
  verificações por IP em 15 minutos e cem solicitações de envio por hora no total.
  A identificação do IP usa `request.client.host`, nunca cabeçalhos fornecidos
  diretamente pelo cliente. Verifique os proxies confiáveis na hospedagem antes
  de ativar; uma configuração incorreta pode compartilhar o limite entre clientes.
- Códigos e identificadores de contato/IP são armazenados como hashes com chave;
  telefone e código não são gravados nas tabelas de recuperação. Janelas de limite
  e desafios com mais de um dia são removidos em novas solicitações.
- Apenas as próximas vinte reservas futuras ativas daquele telefone e daquela
  barbearia são recuperadas. Números formatados com ou sem DDI são reconhecidos;
  dados antigos com número errado precisam ser corrigidos pelo proprietário.
- Falha de envio invalida o código gerado; uma falha atrasada não invalida um código
  novo. Não há exposição de códigos de desenvolvimento, nem gravação de códigos,
  tokens ou telefones nos logs.
- O acesso recuperado utiliza os mesmos tokens públicos de reserva já existentes.
  Confirmar, cancelar ou reagendar continua sendo uma ação explícita. A lista local
  é opcional; se o armazenamento estiver bloqueado, a consulta ainda funciona.

## Validação

Os testes de interface usam dados fictícios e verificam erro de código, validade,
reenvio, consulta e armazenamento bloqueado em celular e computador. Os testes
Python usam transporte simulado da Meta; não enviam mensagens reais.

Execute `scripts/test_tenant_isolation.py` no ambiente local para verificar também
em PostgreSQL isolado: migração, concorrência de consumo do código, isolamento de
telefone e barbearia, filtro de reservas e invalidação após falha de envio.
O GitHub Actions executa o mesmo conjunto com PostgreSQL de serviço.

Em 27/10/2026, André executou o script local com Docker: as migrações foram
aplicadas até `4e5f6a7b8c9d` e os quatro testes de integração passaram em 5,53 s.
Foram validados isolamento entre empresas, recuperação por WhatsApp com envio
simulado, ciclo do agendamento público e assistente com modelo simulado.
O script confirmou a remoção do container e banco temporários, sem criar volumes.
Essa execução valida o fluxo persistente de recuperação; não comprova entrega
de mensagens reais nem aprovação do modelo na Meta.

O teste real de entrega na Meta e a aprovação do modelo permanecem pendentes até
configurar a conta. Não habilite o recurso apenas porque os testes simulados passaram.

Em 27/10/2026, o teste de entrega da conta de teste da Meta retornou `130497` no
webhook, com descrição de restrição de envio para o país do destinatário. Os painéis
consultados mostraram a conta sem problemas de política e o número conectado, com
qualidade alta. A relação alegada pelo atendimento automático com uma dívida da
conta de anúncios não foi tecnicamente comprovada. André deixou a regularização
desse débito para 02/11/2026; a investigação e ativação do envio ficam pendentes.
Não há garantia registrada de que o pagamento resolverá o erro. As demais frentes
do projeto continuam, e `WHATSAPP_RECOVERY_ENABLED` deve permanecer desativado.
