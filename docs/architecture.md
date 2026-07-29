# Arquitetura inicial

## Objetivo

O Projeto Osiris é uma plataforma de agentes de IA para atendimento e agendamento.
A primeira vertical é a de barbearias, mas as regras de negócio devem permitir a
evolução para outros serviços baseados em agenda.

## Camadas

| Camada | Responsabilidade |
| --- | --- |
| `api` | Contratos HTTP, validação de entrada e respostas. |
| `services` | Casos de uso e regras de negócio. |
| `repositories` | Acesso a dados, sem regras de negócio. |
| `models` | Entidades persistidas com SQLAlchemy. |
| `schemas` | Contratos tipados da API com Pydantic. |
| `integrations` | Adaptadores para WhatsApp, OpenAI e Google Calendar. |
| `agents` e `prompts` | Orquestração de IA e instruções versionadas. |
| `core` | Configuração e componentes transversais. |

As rotas nunca devem conversar diretamente com integrações ou banco de dados;
elas delegam aos serviços. Isso preserva testabilidade e permite trocar um
provedor externo sem reescrever a API.

## Próximos componentes

Na Sprint 1, serão adicionados a sessão assíncrona do SQLAlchemy, Alembic e as
primeiras entidades de negócio.
