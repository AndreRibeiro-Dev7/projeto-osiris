from typing import Any

from app.main import app


def test_appointment_status_routes_document_domain_errors() -> None:
    schema: dict[str, Any] = app.openapi()
    paths = schema["paths"]

    for action in ("confirm", "cancel"):
        path = f"/api/v1/businesses/{{business_id}}/appointments/{{appointment_id}}/{action}"
        route = paths[path]
        responses = route["patch"]["responses"]

        assert "404" in responses
        assert "409" in responses
        assert responses["409"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponse"
        }


def test_availability_routes_are_exposed() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/businesses/{business_id}/barbers/{barber_id}/schedule/{weekday}" in paths
    assert "/api/v1/businesses/{business_id}/barbers/{barber_id}/schedule" in paths
    assert "/api/v1/businesses/{business_id}/barbers/{barber_id}/availability" in paths
    assert "/api/v1/businesses/{business_id}/assistant/messages" in paths
    assert "/api/v1/auth/token" in paths
    assert "/api/v1/auth/me" in paths


def test_restricted_barber_routes_are_exposed() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/auth/barber-accounts" in paths
    assert "/api/v1/auth/barber/profile" in paths
    assert "/api/v1/auth/barber/appointments" in paths
    assert "/api/v1/auth/barber/appointments/{appointment_id}/confirm" in paths
    assert "/api/v1/auth/barber/appointments/{appointment_id}/complete" in paths
    assert "/api/v1/auth/barber/appointments/{appointment_id}/no-show" in paths


def test_customer_update_route_is_exposed() -> None:
    route = app.openapi()["paths"]["/api/v1/businesses/{business_id}/customers/{customer_id}"]

    assert "patch" in route
    assert "404" in route["patch"]["responses"]
    assert "409" in route["patch"]["responses"]


def test_customer_portfolio_routes_are_exposed() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/businesses/{business_id}/customers/portfolio" in paths
    assert "/api/v1/businesses/{business_id}/customers.xlsx" in paths
    assert "/api/v1/businesses/{business_id}/customers/{customer_id}/loyalty/redeem" in paths
