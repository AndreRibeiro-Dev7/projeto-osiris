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
    assert "/api/v1/businesses/{business_id}/barbers/{barber_id}/availability" in paths
