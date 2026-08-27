# 🐛 Bug Fix — HTTP 500 na consulta de agendamentos

## 📌 Contexto

Durante os testes da API do **Projeto Osiris**, identifiquei um erro no endpoint responsável por consultar os agendamentos de um barbeiro em uma determinada data.

## ❌ Problema

A requisição:

```http
GET /api/v1/businesses/{business_id}/barbers/{barber_id}/appointments
```

com o parâmetro:

```text id="f44lxj"
appointment_date=2026-08-10
```

estava retornando:

```text id="36ygvl"
HTTP 500 — Internal Server Error
```

### Evidência

![Erro 500 na consulta de agendamentos](../images/erro-500-agendamentos.png)

---

## 🔎 Investigação

Como a rota estava sendo reconhecida corretamente pelo FastAPI, o problema estava ocorrendo durante o processamento interno da requisição.

A investigação apontou para uma dependência necessária ao tratamento de fusos horários no ambiente Windows.

## 🧩 Causa

O ambiente de desenvolvimento não estava com todas as dependências necessárias corretamente instaladas, causando uma exceção durante uma operação relacionada a timezone.

## 🔧 Correção

Com a API parada, as dependências do projeto foram reinstaladas/atualizadas:

```powershell id="odg3us"
.\.venv\Scripts\python.exe -m pip install -e .
```

Depois, a API foi iniciada novamente:

```powershell id="5e5s2v"
.\.venv\Scripts\fastapi.exe dev app/main.py
```

## 🧪 Validação

Após a correção, executei novamente exatamente a mesma requisição.

### Antes

```text id="9bttzc"
HTTP 500 — Internal Server Error
```

### Depois

```text id="ldu1ya"
HTTP 200 — Successful Response
```

A API passou a retornar corretamente o agendamento em formato JSON.

### Evidência da correção

![Consulta de agendamentos funcionando](../images/agendamentos-http-200.png)

---

## 📚 Aprendizados

- Investigar o traceback antes de alterar o código.
- Nem todo erro `500` é causado diretamente pela lógica do endpoint.
- Dependências e diferenças entre ambientes podem afetar a aplicação.
- Repetir o mesmo cenário após a correção é fundamental para validar o bug fix.
- Documentar problemas e soluções cria um histórico técnico útil para o projeto.

## ✅ Status

**Resolvido — HTTP 500 → HTTP 200**
