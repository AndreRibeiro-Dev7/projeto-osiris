# ADR 0001: arquitetura em camadas

- **Status:** Aceita
- **Data:** 2026-07-28

## Contexto

O sistema integrará canais externos, IA, agenda e dados relacionais. Misturar
essas responsabilidades nas rotas HTTP tornaria testes e manutenção caros.

## Decisão

Adotaremos uma arquitetura em camadas: API, serviços, repositórios, modelos e
integrações. Dependências externas serão acessadas por adaptadores em
`app/integrations`.

## Consequências

Há mais arquivos no início do projeto, mas cada responsabilidade fica clara e
as regras de negócio poderão ser testadas sem rede, WhatsApp, OpenAI ou Google.
