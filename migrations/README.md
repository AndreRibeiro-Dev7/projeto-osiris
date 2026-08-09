# Migrações

O Alembic versiona mudanças no schema do PostgreSQL. Nunca altere o banco
manualmente em ambientes compartilhados: descreva a mudança em um modelo e gere
uma migração.

```powershell
# Criar uma revisão após alterar modelos SQLAlchemy
alembic revision --autogenerate -m "describe schema change"

# Aplicar todas as revisões pendentes
alembic upgrade head
```
