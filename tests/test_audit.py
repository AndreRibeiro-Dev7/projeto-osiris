from app.services.audit import describe_activity


def test_audit_describes_owner_account_deletion() -> None:
    area, description = describe_activity("DELETE", "/api/v1/auth/owner-accounts/123")

    assert area == "Contas"
    assert description == "Excluiu o acesso de um coproprietário"


def test_audit_describes_expense_payment() -> None:
    area, description = describe_activity("PATCH", "/api/v1/businesses/123/expenses/456/paid")

    assert area == "Financeiro"
    assert description == "Confirmou o pagamento de uma despesa"


def test_audit_describes_appointment_completion() -> None:
    area, description = describe_activity(
        "PATCH", "/api/v1/businesses/123/appointments/456/complete"
    )

    assert area == "Agenda"
    assert description == "Concluiu um atendimento"
