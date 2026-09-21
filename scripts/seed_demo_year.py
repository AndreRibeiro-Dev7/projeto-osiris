"""Populate one business with a realistic 2026 demonstration year.

The script is idempotent: it refuses to run when demo records already exist and
never deletes user-created appointments, customers, or expenses.
"""

from __future__ import annotations

import argparse
import asyncio
import calendar
import random
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.database.session import async_session_factory
from app.models.appointment import Appointment, AppointmentStatus, PaymentMethod
from app.models.barber import Barber
from app.models.business import Business
from app.models.customer import Customer
from app.models.expense import Expense
from app.models.service import Service

YEAR = 2026
MARKER = "[DEMO OSIRIS 2026]"
GREEN_MONTHS = {1, 3, 4, 6, 7, 9, 10, 12}
RED_MONTHS = {2, 5, 8, 11}
CUSTOMER_NAMES = [
    "Lucas Almeida",
    "Rafael Martins",
    "Bruno Ferreira",
    "Gabriel Souza",
    "Matheus Oliveira",
    "Felipe Santos",
    "Diego Rodrigues",
    "Thiago Lima",
    "Gustavo Ribeiro",
    "Leonardo Costa",
    "André Carvalho",
    "Caio Moreira",
    "Vinícius Rocha",
    "Eduardo Barbosa",
    "Henrique Alves",
    "Daniel Mendes",
    "Marcelo Nunes",
    "Rodrigo Freitas",
    "João Cardoso",
    "Pedro Teixeira",
    "Samuel Araújo",
    "Murilo Correia",
    "Igor Monteiro",
    "Renato Vieira",
]
EXPENSE_TEMPLATES = [
    ("rent", "Aluguel do salão", True),
    ("supplies", "Produtos e materiais profissionais", False),
    ("utilities", "Energia, água e internet", True),
    ("marketing", "Divulgação e anúncios", False),
    ("taxes", "Impostos e taxas", False),
]


def month_weekdays(month: int) -> list[date]:
    return [
        date(YEAR, month, day)
        for day in range(1, calendar.monthrange(YEAR, month)[1] + 1)
        if date(YEAR, month, day).weekday() < 6
    ]


async def seed(apply: bool, business_id: str | None) -> None:
    random.seed(20260920)
    async with async_session_factory() as session:
        business_query = select(Business)
        if business_id:
            from uuid import UUID

            business_query = business_query.where(Business.id == UUID(business_id))
        business = (await session.scalars(business_query.order_by(Business.created_at))).first()
        if business is None:
            raise RuntimeError("Nenhuma barbearia cadastrada.")

        barbers = list(
            await session.scalars(
                select(Barber).where(Barber.business_id == business.id).order_by(Barber.full_name)
            )
        )
        services = list(
            await session.scalars(
                select(Service)
                .where(Service.business_id == business.id, Service.is_active.is_(True))
                .order_by(Service.name)
            )
        )
        customers = list(
            await session.scalars(
                select(Customer)
                .where(Customer.business_id == business.id)
                .order_by(Customer.created_at)
            )
        )
        if not barbers or not services:
            raise RuntimeError(
                "Cadastre ao menos um profissional e um serviço antes de gerar a demonstração."
            )

        demo_count = await session.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.business_id == business.id, Appointment.notes == MARKER)
        )
        demo_expenses = await session.scalar(
            select(func.count())
            .select_from(Expense)
            .where(Expense.business_id == business.id, Expense.description.like(f"{MARKER}%"))
        )
        if demo_count or demo_expenses:
            message = (
                f"A demonstração de 2026 já existe ({demo_count} agendamentos "
                f"e {demo_expenses} despesas)."
            )
            raise RuntimeError(message)

        print(f"Barbearia: {business.name}")
        print(f"Profissionais: {len(barbers)} | Serviços: {len(services)}")
        print(f"Clientes existentes: {len(customers)}")
        if not apply:
            print("Simulação aprovada. Execute novamente com --apply para gravar os dados.")
            return

        existing_phones = {customer.phone for customer in customers}
        for index, name in enumerate(CUSTOMER_NAMES, start=1):
            phone = f"+551199880{index:04d}"
            if phone not in existing_phones:
                customer = Customer(
                    business_id=business.id,
                    full_name=name,
                    phone=phone,
                    notes=f"Cliente de demonstração {MARKER}",
                    birth_date=date(1985 + index % 18, index % 12 + 1, index % 27 + 1),
                )
                session.add(customer)
                customers.append(customer)
        await session.flush()

        timezone_name = ZoneInfo(business.timezone)
        occupied = set(
            await session.scalars(
                select(Appointment.starts_at).where(
                    Appointment.business_id == business.id,
                    Appointment.starts_at >= datetime(YEAR, 1, 1, tzinfo=UTC),
                    Appointment.starts_at < datetime(YEAR + 1, 1, 1, tzinfo=UTC),
                )
            )
        )
        monthly_revenue: dict[int, int] = {month: 0 for month in range(1, 13)}
        appointment_total = 0
        payment_methods = list(PaymentMethod)
        base_per_barber = [24, 20, 28, 26, 18, 30, 27, 23, 29, 31, 21, 32]

        for month in range(1, 13):
            days = month_weekdays(month)
            for barber_index, barber in enumerate(barbers):
                target = base_per_barber[month - 1] + barber_index * 2
                for sequence in range(target):
                    service = services[(sequence + barber_index + month) % len(services)]
                    day = days[(sequence * 3 + barber_index * 5) % len(days)]
                    hour = 9 + (sequence % 8)
                    minute = 30 if (sequence // 8) % 2 else 0
                    local_start = datetime.combine(day, time(hour, minute), tzinfo=timezone_name)
                    starts_at = local_start.astimezone(UTC)
                    while starts_at in occupied:
                        local_start += timedelta(minutes=15)
                        starts_at = local_start.astimezone(UTC)
                    occupied.add(starts_at)
                    status_roll = sequence % 20
                    status = (
                        AppointmentStatus.NO_SHOW
                        if status_roll == 18
                        else AppointmentStatus.CANCELLED
                        if status_roll == 19
                        else AppointmentStatus.COMPLETED
                    )
                    price = service.price_cents + (
                        500 if month in {6, 7, 12} and status == AppointmentStatus.COMPLETED else 0
                    )
                    appointment = Appointment(
                        business_id=business.id,
                        barber_id=barber.id,
                        customer_id=customers[
                            (sequence + month * 3 + barber_index) % len(customers)
                        ].id,
                        service_id=service.id,
                        price_cents=price,
                        payment_method=payment_methods[(sequence + month) % len(payment_methods)]
                        if status == AppointmentStatus.COMPLETED
                        else None,
                        paid_at=(starts_at + timedelta(minutes=service.duration_minutes))
                        if status == AppointmentStatus.COMPLETED
                        else None,
                        starts_at=starts_at,
                        ends_at=starts_at + timedelta(minutes=service.duration_minutes),
                        status=status,
                        notes=MARKER,
                    )
                    session.add(appointment)
                    appointment_total += 1
                    if status == AppointmentStatus.COMPLETED:
                        monthly_revenue[month] += price

        await session.flush()
        average_commission = (
            sum(barber.commission_percentage for barber in barbers) / len(barbers) / 100
        )
        expense_total = 0
        monthly_results: list[tuple[int, int, int, int]] = []
        for month in range(1, 13):
            revenue = monthly_revenue[month]
            net_after_commission = round(revenue * (1 - average_commission))
            target_expenses = round(
                net_after_commission * (0.55 if month in GREEN_MONTHS else 1.25)
            )
            weights = [0.34, 0.25, 0.16, 0.10, 0.15]
            amounts = [round(target_expenses * weight) for weight in weights]
            amounts[-1] += target_expenses - sum(amounts)
            for day, ((category, description, is_fixed), amount) in enumerate(
                zip(EXPENSE_TEMPLATES, amounts, strict=True), start=4
            ):
                paid = not (month == 9 and category in {"marketing", "taxes"})
                session.add(
                    Expense(
                        business_id=business.id,
                        category=category,
                        description=f"{MARKER} {description}",
                        amount_cents=max(amount, 100),
                        occurred_on=date(YEAR, month, min(day * 2, 25)),
                        is_fixed=is_fixed,
                        is_paid=paid,
                        paid_at=datetime(YEAR, month, min(day * 2, 25), 15, tzinfo=UTC)
                        if paid
                        else None,
                    )
                )
                expense_total += 1
            result = net_after_commission - target_expenses
            monthly_results.append((month, revenue, target_expenses, result))

        await session.commit()
        print(f"Criados: {appointment_total} agendamentos e {expense_total} despesas.")
        print("Resultado estimado após comissões:")
        for month, revenue, expenses, result in monthly_results:
            color = "VERDE" if result >= 0 else "VERMELHO"
            values = (
                f"receita R$ {revenue / 100:,.2f} | "
                f"despesas R$ {expenses / 100:,.2f} | "
                f"resultado R$ {result / 100:,.2f}"
            )
            print(f"  {month:02d}/{YEAR}: {values} [{color}]")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Grava os dados no banco")
    parser.add_argument("--business-id", help="UUID da barbearia; usa a primeira quando omitido")
    args = parser.parse_args()
    asyncio.run(seed(args.apply, args.business_id))


if __name__ == "__main__":
    main()
