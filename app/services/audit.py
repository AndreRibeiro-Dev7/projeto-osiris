"""Automatic descriptions and persistence for authenticated activity."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User


def describe_activity(method: str, path: str) -> tuple[str, str]:
    """Translate one successful API mutation into a safe user-facing description."""
    method = method.upper()
    if "/owner-accounts" in path:
        descriptions = {
            "POST": "Criou uma conta de coproprietário",
            "PATCH": "Alterou o acesso de um coproprietário",
            "DELETE": "Excluiu o acesso de um coproprietário",
        }
        return "Contas", descriptions.get(method, "Alterou contas administrativas")
    if "/barber-accounts" in path:
        descriptions = {
            "POST": "Criou o acesso de um profissional",
            "PATCH": "Alterou o acesso de um profissional",
            "DELETE": "Excluiu o acesso de um profissional",
        }
        return "Contas", descriptions.get(method, "Alterou acessos profissionais")
    if path.endswith("/password"):
        return "Contas", "Alterou a própria senha"
    if "/email/confirm" in path:
        return "Contas", "Confirmou um novo e-mail de acesso"
    if "/email/request" in path:
        return "Contas", "Solicitou a alteração do e-mail de acesso"
    if "/appointments" in path:
        suffixes = {
            "/confirm": "Confirmou um agendamento",
            "/cancel": "Cancelou um agendamento",
            "/complete": "Concluiu um atendimento",
            "/no-show": "Marcou o não comparecimento de um cliente",
            "/reschedule": "Reagendou um atendimento",
            "/notes": "Alterou as observações de um agendamento",
        }
        for suffix, description in suffixes.items():
            if path.endswith(suffix):
                return "Agenda", description
        return "Agenda", "Criou um agendamento" if method == "POST" else "Alterou a agenda"
    if "/expenses" in path:
        if path.endswith("/paid"):
            return "Financeiro", "Confirmou o pagamento de uma despesa"
        if path.endswith("/pending"):
            return "Financeiro", "Marcou uma despesa como pendente"
        if "/fixed/generate" in path:
            return "Financeiro", "Gerou as despesas fixas do próximo mês"
        descriptions = {
            "POST": "Cadastrou uma despesa",
            "PATCH": "Alterou uma despesa",
            "DELETE": "Excluiu uma despesa",
        }
        return "Financeiro", descriptions.get(method, "Alterou dados financeiros")
    if "/loyalty/redeem" in path:
        return "Clientes", "Resgatou uma recompensa de fidelidade"
    if "/customers" in path:
        return (
            "Clientes",
            "Cadastrou um cliente" if method == "POST" else "Alterou um cliente",
        )
    if "/services" in path:
        return (
            "Serviços",
            "Cadastrou um serviço" if method == "POST" else "Alterou um serviço",
        )
    if "/closures" in path:
        return (
            "Fechamentos",
            "Adicionou um fechamento" if method == "POST" else "Excluiu um fechamento",
        )
    if "/barbers" in path:
        if "/schedule/" in path:
            return "Equipe", "Alterou a jornada de um profissional"
        if "/time-off" in path:
            return "Equipe", "Alterou uma folga de profissional"
        return (
            "Equipe",
            "Cadastrou um profissional" if method == "POST" else "Alterou um profissional",
        )
    if path.startswith("/api/v1/businesses/") and method == "PATCH":
        return "Configurações", "Alterou as configurações da barbearia"
    return "Sistema", "Realizou uma alteração no sistema"


async def record_activity(session: AsyncSession, *, user: User, method: str, path: str) -> None:
    """Persist one successful mutation without storing request payloads or credentials."""
    area, description = describe_activity(method, path)
    session.add(
        AuditLog(
            business_id=user.business_id,
            actor_user_id=user.id,
            actor_email=user.email,
            actor_role=user.role,
            actor_is_primary_owner=user.is_primary_owner,
            area=area,
            description=description,
            method=method.upper(),
            path=path,
        )
    )
    await session.commit()
