"""Create an idempotent, realistic three-year history for one business."""

from __future__ import annotations

import argparse
import asyncio
import calendar
import random
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.database.session import async_session_factory
from app.models.appointment import Appointment, AppointmentStatus, PaymentMethod
from app.models.barber import Barber
from app.models.barber_schedule import BarberSchedule
from app.models.business import Business
from app.models.customer import Customer
from app.models.expense import Expense
from app.models.service import Service

START_YEAR = 2025
END_YEAR = 2027
MARKER = "[SIMULACAO OSIRIS 2025-2027]"
MONTH_FACTORS = (0.86, 0.93, 1.04, 1.12, 0.97, 1.08, 1.16, 0.89, 1.03, 1.11, 0.95, 1.22)
YEAR_FACTORS = {2025: 0.94, 2026: 1.00, 2027: 1.06}
RED_RESULT_MONTHS = {2, 5, 8, 11}
BARBER_NAMES = ("André Ribeiro", "Carlos Mendes", "Felipe Rocha", "Rafael Lima", "Bruno Alves")
CUSTOMER_NAMES = (
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
    "Alexandre Castro",
    "Leandro Moraes",
    "Fábio Duarte",
    "Márcio Pires",
    "César Ramos",
    "Otávio Freire",
    "Vitor Hugo",
    "Wesley Gomes",
    "Danilo Cunha",
    "Fernando Braga",
    "Júlio César",
    "Ricardo Lopes",
    "Roberto Dias",
    "Paulo Viana",
    "Sérgio Reis",
    "Márcio Silva",
    "Alan Tavares",
    "Alex Sandro",
    "Cristiano Melo",
    "Everton Prado",
    "Flávio Peixoto",
    "Gilberto Neves",
    "Hugo Farias",
    "Jorge Xavier",
    "Kleber Moura",
    "Luan Campos",
    "Maurício Dantas",
    "Nicolas Azevedo",
    "Orlando Maia",
    "Patrick Correia",
    "Ramon Soares",
    "Sandro Nascimento",
    "Tales Brito",
    "Valter Aquino",
    "William Nogueira",
    "Yuri Rezende",
    "Adriano Coelho",
    "Breno Paiva",
    "Cláudio Matos",
    "Douglas Assis",
    "Elias Barros",
    "Francisco Leal",
    "Geovane Sales",
    "Heitor Amorim",
    "Ismael Pinto",
    "Jefferson Luz",
    "Kevin Macedo",
    "Luiz Henrique",
    "Nathan Porto",
    "Pablo Rios",
    "Renan Teodoro",
)
SERVICE_CATALOG = (
    ("Corte tradicional", "Corte masculino completo", 45, 6000),
    ("Barba", "Modelagem e acabamento da barba", 30, 4000),
    ("Corte + barba", "Combo completo", 60, 9000),
    ("Degradê premium", "Degradê com acabamento premium", 60, 7500),
    ("Sobrancelha", "Acabamento de sobrancelha", 20, 2500),
)
EXPENSES = (
    ("rent", "Aluguel do salão", True, 0.28),
    ("supplies", "Produtos e materiais", False, 0.22),
    ("utilities", "Energia, água e internet", True, 0.14),
    ("taxes", "Impostos e taxas", False, 0.18),
    ("marketing", "Marketing e divulgação", False, 0.08),
    ("maintenance", "Manutenção e despesas diversas", False, 0.10),
)


def working_days(year: int, month: int) -> list[date]:
    return [
        date(year, month, day)
        for day in range(1, calendar.monthrange(year, month)[1] + 1)
        if date(year, month, day).weekday() < 6
    ]


async def seed(business_id: str | None = None) -> None:
    rng = random.Random(20250922)
    async with async_session_factory() as session:
        query = select(Business).order_by(Business.created_at)
        if business_id:
            query = query.where(Business.id == UUID(business_id))
        business = (await session.scalars(query)).first()
        if business is None:
            raise RuntimeError("Nenhuma barbearia cadastrada.")

        existing_demo = await session.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.business_id == business.id, Appointment.notes == MARKER)
        )
        if existing_demo:
            print(f"A simulação já existe ({existing_demo} atendimentos). Nada foi duplicado.")
            return

        business.monthly_revenue_goal_cents = 5_000_000
        barbers = list(
            await session.scalars(
                select(Barber).where(Barber.business_id == business.id).order_by(Barber.created_at)
            )
        )
        existing_barber_phones = {item.phone for item in barbers}
        for index, name in enumerate(BARBER_NAMES, start=1):
            if len(barbers) >= 5:
                break
            phone = f"+554899900{index:04d}"
            if phone in existing_barber_phones:
                continue
            barber = Barber(
                business_id=business.id,
                full_name=name,
                phone=phone,
                is_active=True,
                commission_percentage=40 + index % 3 * 5,
            )
            session.add(barber)
            barbers.append(barber)
            existing_barber_phones.add(phone)
        selected_barbers = barbers[:5]
        if len(selected_barbers) < 5:
            raise RuntimeError("Não foi possível preparar cinco profissionais.")

        services = list(
            await session.scalars(
                select(Service)
                .where(Service.business_id == business.id)
                .order_by(Service.created_at)
            )
        )
        service_names = {item.name.casefold() for item in services}
        for name, description, duration, price in SERVICE_CATALOG:
            if name.casefold() in service_names:
                continue
            service = Service(
                business_id=business.id,
                name=name,
                description=description,
                duration_minutes=duration,
                price_cents=price,
                is_active=True,
            )
            session.add(service)
            services.append(service)
        demo_services = [item for item in services if item.is_active and item.price_cents > 0]
        if not demo_services:
            raise RuntimeError("Nenhum serviço com preço foi encontrado.")

        customers = list(
            await session.scalars(
                select(Customer)
                .where(Customer.business_id == business.id)
                .order_by(Customer.created_at)
            )
        )
        existing_customer_phones = {item.phone for item in customers}
        for index, name in enumerate(CUSTOMER_NAMES, start=1):
            if len(customers) >= 80:
                break
            phone = f"+554898800{index:04d}"
            if phone in existing_customer_phones:
                continue
            customer = Customer(
                business_id=business.id,
                full_name=name,
                phone=phone,
                notes=f"Cliente da simulação histórica {MARKER}",
                birth_date=date(1978 + index % 28, index % 12 + 1, index % 27 + 1),
            )
            session.add(customer)
            customers.append(customer)
            existing_customer_phones.add(phone)

        await session.flush()
        schedule_pairs = set(
            (
                await session.execute(
                    select(BarberSchedule.barber_id, BarberSchedule.weekday).where(
                        BarberSchedule.barber_id.in_([barber.id for barber in selected_barbers])
                    )
                )
            ).all()
        )
        for barber in selected_barbers:
            for weekday in range(6):
                if (barber.id, weekday) not in schedule_pairs:
                    session.add(
                        BarberSchedule(
                            barber_id=barber.id,
                            weekday=weekday,
                            starts_at=time(9),
                            ends_at=time(19),
                            break_starts_at=time(12),
                            break_ends_at=time(13),
                            slot_duration_minutes=60,
                        )
                    )

        timezone = ZoneInfo(business.timezone)
        occupied_rows = (
            await session.execute(
                select(Appointment.barber_id, Appointment.starts_at).where(
                    Appointment.business_id == business.id,
                    Appointment.starts_at >= datetime(START_YEAR, 1, 1, tzinfo=UTC),
                    Appointment.starts_at < datetime(END_YEAR + 1, 1, 1, tzinfo=UTC),
                )
            )
        ).all()
        occupied: set[tuple[UUID, datetime]] = {
            (row.barber_id, row.starts_at) for row in occupied_rows
        }
        payment_methods = list(PaymentMethod)
        appointment_count = 0
        expense_count = 0

        for year in range(START_YEAR, END_YEAR + 1):
            for month in range(1, 13):
                revenue_target = round(5_000_000 * MONTH_FACTORS[month - 1] * YEAR_FACTORS[year])
                month_revenue = 0
                slot_sequence = 0
                days = working_days(year, month)
                max_slots = len(days) * len(selected_barbers) * 9
                while month_revenue < revenue_target and slot_sequence < max_slots:
                    day_index = slot_sequence // (len(selected_barbers) * 9)
                    within_day = slot_sequence % (len(selected_barbers) * 9)
                    barber_index = within_day % len(selected_barbers)
                    hour_index = within_day // len(selected_barbers)
                    hour = 9 + hour_index + (1 if hour_index >= 3 else 0)
                    barber = selected_barbers[barber_index]
                    starts_at = datetime.combine(
                        days[day_index], time(hour), tzinfo=timezone
                    ).astimezone(UTC)
                    slot_sequence += 1
                    if (barber.id, starts_at) in occupied:
                        continue
                    occupied.add((barber.id, starts_at))
                    roll = appointment_count % 25
                    status = (
                        AppointmentStatus.CANCELLED
                        if roll == 23
                        else (
                            AppointmentStatus.NO_SHOW if roll == 24 else AppointmentStatus.COMPLETED
                        )
                    )
                    service = rng.choices(
                        demo_services,
                        weights=[max(item.price_cents, 1000) for item in demo_services],
                        k=1,
                    )[0]
                    price = service.price_cents + (
                        500 if month in {6, 7, 12} and status == AppointmentStatus.COMPLETED else 0
                    )
                    customer = customers[(appointment_count * 7 + month + year) % len(customers)]
                    session.add(
                        Appointment(
                            business_id=business.id,
                            barber_id=barber.id,
                            customer_id=customer.id,
                            service_id=service.id,
                            price_cents=price,
                            payment_method=(
                                rng.choice(payment_methods)
                                if status == AppointmentStatus.COMPLETED
                                else None
                            ),
                            paid_at=(
                                starts_at + timedelta(minutes=service.duration_minutes)
                                if status == AppointmentStatus.COMPLETED
                                else None
                            ),
                            starts_at=starts_at,
                            ends_at=starts_at + timedelta(minutes=service.duration_minutes),
                            status=status,
                            notes=MARKER,
                        )
                    )
                    appointment_count += 1
                    if status == AppointmentStatus.COMPLETED:
                        month_revenue += price

                average_commission = (
                    sum(barber.commission_percentage for barber in selected_barbers)
                    / len(selected_barbers)
                    / 100
                )
                net_after_commission = round(month_revenue * (1 - average_commission))
                expense_factor = 1.10 if month in RED_RESULT_MONTHS else rng.uniform(0.68, 0.88)
                expense_target = round(net_after_commission * expense_factor)
                amounts = [round(expense_target * item[3]) for item in EXPENSES]
                amounts[-1] += expense_target - sum(amounts)
                for index, ((category, description, is_fixed, _), amount) in enumerate(
                    zip(EXPENSES, amounts, strict=True), start=1
                ):
                    occurred_on = date(year, month, min(index * 4, 26))
                    session.add(
                        Expense(
                            business_id=business.id,
                            category=category,
                            description=f"{MARKER} {description}",
                            amount_cents=max(amount, 100),
                            occurred_on=occurred_on,
                            is_fixed=is_fixed,
                            is_paid=True,
                            paid_at=datetime.combine(occurred_on, time(15), tzinfo=UTC),
                        )
                    )
                    expense_count += 1

        await session.commit()
        print(
            f"Simulação concluída: {appointment_count} agendamentos, "
            f"{expense_count} despesas, {len(customers)} clientes e "
            f"{len(selected_barbers)} profissionais."
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--business-id")
    args = parser.parse_args()
    asyncio.run(seed(args.business_id))


if __name__ == "__main__":
    main()
