# Publicação do Projeto Osiris

O Osiris pode ser publicado em qualquer plataforma que execute uma imagem
Docker e forneça um PostgreSQL. A imagem já inclui o painel web, executa as
migrações pendentes e inicia a API na porta informada por `PORT`.

## Arquitetura recomendada

- um serviço web executando a imagem criada pelo `Dockerfile`;
- um banco PostgreSQL gerenciado com backup automático;
- domínio com HTTPS administrado pela plataforma;
- segredos armazenados nas variáveis do ambiente de produção.

O PostgreSQL do `docker-compose.yml` é destinado ao desenvolvimento local. Não
publique suas credenciais padrão nem exponha a porta 5432 na internet.

## Variáveis obrigatórias

Configure no painel da hospedagem:

```text
ENVIRONMENT=production
DEBUG=false
DATABASE_ECHO=false
DATABASE_URL=postgresql+asyncpg://USUARIO:SENHA@HOST:5432/BANCO
JWT_SECRET_KEY=uma-chave-aleatoria-longa-e-exclusiva
OPENAI_API_KEY=chave-do-projeto-openai
OPENAI_MODEL=gpt-5.6-luna
EMAIL_DELIVERY_ENABLED=true
RESEND_API_KEY=chave-do-resend
RESEND_FROM_EMAIL=Osiris <contato@seudominio.com.br>
```

Gere a chave JWT localmente sem reutilizar senhas:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Se alguma integração ainda não for usada, mantenha sua chave vazia e o recurso
desativado. Nunca envie o arquivo `.env` para GitHub, chat ou suporte.

## Validar a imagem antes da publicação

Com o Docker Desktop em execução:

```powershell
docker compose build api
docker compose up -d db api
docker compose ps
```

Valide os endereços:

- painel: `http://127.0.0.1:8000/dashboard/`;
- API: `http://127.0.0.1:8000/api/v1/health`;
- banco: `http://127.0.0.1:8000/api/v1/health/database`.

Consulte os logs caso o health check não fique saudável:

```powershell
docker compose logs --tail 100 api
```

## Fluxo de publicação

1. Enviar o repositório privado para o provedor escolhido.
2. Criar o banco PostgreSQL gerenciado.
3. Cadastrar as variáveis de produção no provedor.
4. Publicar usando o `Dockerfile` da raiz.
5. Confirmar os dois endpoints de health check.
6. Vincular domínio e aguardar a emissão do certificado HTTPS.
7. Testar login, agenda, financeiro, e-mail e agendamento público.
8. Configurar alertas e validar o primeiro backup restaurável.

## Publicação inicial no Render

O arquivo `render.yaml` da raiz descreve a API e o PostgreSQL. No painel do
Render, escolha **New > Blueprint**, conecte o repositório e selecione esse
arquivo. Durante a criação, informe os segredos solicitados:

- `OPENAI_API_KEY`;
- `RESEND_API_KEY`;
- `RESEND_FROM_EMAIL`.

A chave JWT é criada automaticamente. A conexão privada do banco também é
preenchida pelo Blueprint e convertida pelo Osiris para o driver `asyncpg`.
O `OWNER_BOOTSTRAP_TOKEN` também é gerado automaticamente e protege a criação
do primeiro proprietário. Depois que uma empresa já possui um proprietário, o
endpoint recusa novas tentativas para ela.

O Blueprint mantém `OWNER_BOOTSTRAP_ENABLED=false`. Para uma instalação nova,
altere temporariamente a variável para `true`, crie o primeiro proprietário e
retorne imediatamente para `false`. Com a variável desativada, o endpoint não
aceita requisições em produção mesmo que alguém conheça um token antigo.

O Blueprint começa nos planos gratuitos para permitir a primeira homologação.
Antes de atender uma barbearia real, altere o serviço e o banco para planos com
disponibilidade e retenção adequadas, além de configurar backup restaurável.

Em produção, Swagger, ReDoc e o schema OpenAPI ficam desativados. O painel e os
endpoints da aplicação permanecem disponíveis normalmente.

## Atualizações e rollback

Cada atualização deve executar os testes antes da publicação. As migrações são
aplicadas automaticamente ao iniciar o contêiner. Antes de uma alteração de
banco relevante, crie um backup e confirme que a versão anterior da imagem
continua disponível para rollback.
