const API = "/api/v1";
const state = { token: sessionStorage.getItem("osiris_token"), me: null, business: null, barbers: [], customers: [], customerPortfolio: [], customerSegment: "all", services: [], appointments: [], bookingSlots: [], financialReport: null, financialChartZoom: 1, financialChartPoints: [], financialChartPeriod: "day", expensePeriodItems: [], homeExpenses: [], expenseAnalysisText: "", personKind: null, editingCustomerId: null, editingBarberId: null, editingServiceId: null, editingExpenseId: null, accessBarberId: null, pendingEmail: null, scheduleBarberId: null, scheduleExistingWeekdays: [], timeOffBarberId: null, detailAppointmentId: null, paymentAppointmentId: null, rescheduleAppointmentId: null, refreshInFlight: false, confirmationResolver: null };
const $ = (id) => document.getElementById(id);
const localDate = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date());
const authHeaders = () => ({ Authorization: `Bearer ${state.token}` });

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, { ...options, headers: { ...authHeaders(), ...(options.headers || {}) } });
  if (response.status === 401) { logout(); throw new Error("Sua sessão expirou. Entre novamente."); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Não foi possível concluir a operação.");
  return data;
}

function showToast(message) { const toast = $("toast"); toast.textContent = message; toast.classList.add("show"); setTimeout(() => toast.classList.remove("show"), 2600); }
function closeConfirmation(result = false) { $("confirmation-modal").hidden = true; document.body.classList.remove("modal-open"); const resolve = state.confirmationResolver; state.confirmationResolver = null; if (resolve) resolve(result); }
function confirmAction({ eyebrow, title, message, detail, confirmLabel, variant = "default" }) {
  if (state.confirmationResolver) closeConfirmation(false);
  $("confirmation-eyebrow").textContent = eyebrow;
  $("confirmation-title").textContent = title;
  $("confirmation-message").textContent = message;
  $("confirmation-detail").textContent = detail;
  $("confirmation-submit-label").textContent = confirmLabel;
  $("confirmation-icon").textContent = variant === "danger" ? "!" : "✓";
  $("confirmation-modal").querySelector(".confirmation-modal").classList.toggle("danger", variant === "danger");
  $("confirmation-modal").hidden = false;
  document.body.classList.add("modal-open");
  setTimeout(() => $("confirmation-submit").focus(), 0);
  return new Promise((resolve) => { state.confirmationResolver = resolve; });
}
function initials(name) { return name.split(" ").slice(0, 2).map((part) => part[0]).join("").toUpperCase(); }
function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]); }
function statusLabel(status) { return ({ scheduled: "Agendado", confirmed: "Confirmado", cancelled: "Cancelado", completed: "Concluído", no_show: "Não compareceu" })[status] || status; }
function formatTime(value) { return new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: state.business?.timezone || "America/Sao_Paulo" }).format(new Date(value)); }
function formatAppointmentDate(value) { return new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "2-digit", month: "2-digit", timeZone: state.business?.timezone || "America/Sao_Paulo" }).format(new Date(value)); }

async function login(event) {
  event.preventDefault(); $("login-error").textContent = ""; $("login-button").disabled = true; $("login-button-label").textContent = "Entrando...";
  const body = new URLSearchParams({ username: $("email").value.trim(), password: $("password").value });
  try {
    const response = await fetch(`${API}/auth/token`, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body });
    const raw = await response.text(); let data = {}; try { data = JSON.parse(raw); } catch { data = { detail: response.ok ? raw : "O servidor não conseguiu acessar o banco de dados." }; } if (!response.ok) throw new Error(data.detail || "E-mail ou senha incorretos.");
    state.token = data.access_token; sessionStorage.setItem("osiris_token", state.token); await boot();
  } catch (error) { $("login-error").textContent = error.message === "Incorrect email or password." ? "E-mail ou senha incorretos." : error.message; }
  finally { $("login-button").disabled = false; $("login-button-label").textContent = "Entrar no painel"; }
}

async function boot() {
  $("login-view").hidden = true; $("app-view").hidden = true; $("loading-view").hidden = false;
  try {
    state.me = await request("/auth/me");
    if (state.me.role === "barber") { await bootBarber(); return; }
    [state.business, state.barbers, state.customers, state.customerPortfolio, state.services] = await Promise.all([
      request(`/businesses/${state.me.business_id}`), request(`/businesses/${state.me.business_id}/barbers`), request(`/businesses/${state.me.business_id}/customers`), request(`/businesses/${state.me.business_id}/customers/portfolio`), request(`/businesses/${state.me.business_id}/services`)
    ]);
    document.body.classList.remove("barber-session"); document.querySelectorAll(".nav-item").forEach((button) => { button.hidden = false; button.classList.toggle("active", button.dataset.view === "inicio"); }); document.querySelectorAll(".panel-view").forEach((panel) => { panel.hidden = panel.id !== "inicio-panel"; }); $("barber-filter").disabled = false; $("new-appointment").hidden = false; $("save-appointment-notes").hidden = false; document.querySelector("#agenda-panel .title-row h1").textContent = "Agenda"; document.querySelector("#agenda-panel .title-row .muted").textContent = "Organize os atendimentos por profissional e data.";
    $("loading-view").hidden = true; $("app-view").hidden = false; window.scrollTo(0, 0); $("user-email").textContent = state.me.email; $("business-name").textContent = state.business.name;
    $("business-settings-name").value = state.business.name; $("business-settings-phone").value = state.business.phone; $("business-settings-timezone").value = state.business.timezone; $("loyalty-enabled").checked = state.business.loyalty_enabled; $("loyalty-target").value = state.business.loyalty_target; $("loyalty-reward").value = state.business.loyalty_reward; $("revenue-goal-input").value = (state.business.monthly_revenue_goal_cents / 100).toFixed(2); $("current-email").value = state.me.email; $("save-email-label").textContent = "Enviar código";
    const publicLink = `${location.origin}/dashboard/booking/?business_id=${state.me.business_id}`; $("public-booking-link").value = publicLink; $("open-booking-link").href = publicLink;
    $("barber-filter").innerHTML = `<option value="all">Todos os profissionais</option>${state.barbers.map((b) => `<option value="${b.id}">${escapeHtml(b.full_name)}</option>`).join("")}`;
    renderPeople(); renderCustomerRanking(); await loadAgenda(); await loadHome();
  } catch (error) { logout(); $("login-error").textContent = error.message; }
}

async function bootBarber() {
  const profile = await request("/auth/barber/profile");
  state.business = { id: profile.business_id, name: profile.business_name, timezone: profile.timezone };
  state.barbers = [{ id: profile.barber_id, full_name: profile.full_name, phone: profile.phone, commission_percentage: profile.commission_percentage, is_active: true }];
  state.customers = []; state.services = [];
  $("loading-view").hidden = true; $("app-view").hidden = false; window.scrollTo(0, 0);
  $("user-email").textContent = state.me.email; $("business-name").textContent = `${profile.business_name} · ${profile.full_name}`;
  document.body.classList.add("barber-session");
  document.querySelectorAll(".nav-item").forEach((button) => { button.hidden = button.dataset.view !== "agenda"; button.classList.toggle("active", button.dataset.view === "agenda"); });
  document.querySelectorAll(".panel-view").forEach((panel) => { panel.hidden = panel.id !== "agenda-panel"; });
  $("barber-filter").innerHTML = `<option value="${profile.barber_id}">${escapeHtml(profile.full_name)}</option>`; $("barber-filter").disabled = true;
  $("new-appointment").hidden = true; $("save-appointment-notes").hidden = true;
  document.querySelector("#agenda-panel .title-row h1").textContent = "Minha agenda";
  document.querySelector("#agenda-panel .title-row .muted").textContent = `Atendimentos de ${profile.full_name} · comissão ${profile.commission_percentage}%`;
  await loadAgenda();
}

async function refreshReferenceData() {
  const selectedBarber = $("barber-filter").value || "all";
  [state.business, state.barbers, state.customers, state.customerPortfolio, state.services] = await Promise.all([
    request(`/businesses/${state.me.business_id}`),
    request(`/businesses/${state.me.business_id}/barbers`),
    request(`/businesses/${state.me.business_id}/customers`),
    request(`/businesses/${state.me.business_id}/customers/portfolio`),
    request(`/businesses/${state.me.business_id}/services`),
  ]);
  $("business-name").textContent = state.business.name;
  $("barber-filter").innerHTML = `<option value="all">Todos os profissionais</option>${state.barbers.map((barber) => `<option value="${barber.id}">${escapeHtml(barber.full_name)}</option>`).join("")}`;
  $("barber-filter").value = state.barbers.some((barber) => barber.id === selectedBarber) ? selectedBarber : "all";
  renderPeople();
  renderCustomerRanking();
}

async function refreshActiveView() {
  if (!state.token || !state.me || state.refreshInFlight || $("app-view").hidden || document.hidden) return;
  state.refreshInFlight = true;
  try {
    if (state.me.role === "barber") { await loadAgenda(); return; }
    await refreshReferenceData();
    const view = document.querySelector(".nav-item.active")?.dataset.view || "inicio";
    if (view === "inicio") await loadHome();
    else if (view === "agenda") await loadAgenda();
    else if (view === "financeiro") await loadFinancial();
    else if (view === "clientes") await loadCustomerPortfolio();
    else if (view === "fechamentos") await loadClosures();
  } catch (error) { showToast(error.message); }
  finally { state.refreshInFlight = false; }
}

async function loadHome() {
  let appointments = state.appointments;
  try { appointments = (await fetchAgendaSnapshot(localDate(), "all", false)).appointments; }
  catch { /* Keep the last known snapshot if the network is temporarily unavailable. */ }
  const hour = new Date().getHours();
  $("home-greeting").textContent = `${hour < 12 ? "Bom dia" : hour < 18 ? "Boa tarde" : "Boa noite"}, ${state.business.name}.`;
  const activeBarbers = state.barbers.filter((item) => item.is_active).length;
  const confirmed = appointments.filter((item) => item.status === "confirmed").length;
  $("home-appointments").textContent = appointments.length;
  $("home-confirmed").textContent = `${confirmed} confirmado${confirmed === 1 ? "" : "s"} para hoje`;
  $("home-customers").textContent = state.customers.length;
  $("home-barbers").textContent = activeBarbers;
  const scheduled = appointments.filter((item) => item.status === "scheduled").length;
  const noShows = appointments.filter((item) => item.status === "no_show").length;
  const alerts = [];
  if (scheduled) alerts.push({ icon: "!", title: `${scheduled} aguardando confirmação`, detail: "Confirme os horários antes do atendimento.", view: "agenda" });
  if (noShows) alerts.push({ icon: "!", title: `${noShows} não compareceu${noShows === 1 ? "" : "ram"}`, detail: "Revise as faltas registradas hoje.", view: "agenda" });
  const upcoming = appointments.filter((item) => !["cancelled", "completed", "no_show"].includes(item.status)).slice(0, 5);
  $("home-next-appointments").innerHTML = upcoming.length ? upcoming.map((item) => { const customer = state.customers.find((entry) => entry.id === item.customer_id); const barber = state.barbers.find((entry) => entry.id === item.barber_id); const service = state.services.find((entry) => entry.id === item.service_id); return `<article class="home-appointment"><strong>${formatTime(item.starts_at)}</strong><div><strong>${escapeHtml(customer?.full_name || "Cliente")}</strong><span>${escapeHtml(service?.name || "Serviço")} · ${escapeHtml(barber?.full_name || "Profissional")}</span></div><span class="badge ${item.status}">${statusLabel(item.status)}</span></article>`; }).join("") : '<div class="empty">Nenhum atendimento pendente para hoje.</div>';
  const today = localDate(), monthStart = `${today.slice(0, 8)}01`;
  const daysInMonth = new Date(Number(today.slice(0, 4)), Number(today.slice(5, 7)), 0).getDate();
  const monthEnd = `${today.slice(0, 8)}${String(daysInMonth).padStart(2, "0")}`;
  try {
    const [report, monthlyExpenses] = await Promise.all([
      request(`/businesses/${state.me.business_id}/reports/financial?date_from=${monthStart}&date_to=${today}`),
      request(`/businesses/${state.me.business_id}/expenses?date_from=${monthStart}&date_to=${monthEnd}`),
    ]);
    state.homeExpenses = monthlyExpenses;
    $("home-revenue").textContent = formatMoney(report.total_revenue_cents);
    const goal = state.business.monthly_revenue_goal_cents || 0;
    $("home-goal").textContent = goal ? `${Math.min(100, Math.round(report.total_revenue_cents / goal * 100))}% da meta mensal` : "meta mensal não definida";
    monthlyExpenses.filter((expense) => !expense.is_paid).sort((a, b) => a.occurred_on.localeCompare(b.occurred_on)).forEach((expense) => alerts.push({
      icon: "−",
      title: `${expense.description} · ${formatMoney(expense.amount_cents)}`,
      detail: `${expense.is_fixed ? "Despesa fixa" : "Despesa"} · ${expenseDueLabel(expense)}.`,
      view: "financeiro",
      expenseId: expense.id,
      urgent: expense.occurred_on < today,
    }));
    const currentDay = Number(today.slice(-2));
    if (goal && report.total_revenue_cents < goal * currentDay / daysInMonth) alerts.push({ icon: "↘", title: "Meta abaixo do ritmo", detail: `${formatMoney(report.total_revenue_cents)} faturados neste mês.`, view: "financeiro" });
  } catch { $("home-revenue").textContent = "—"; $("home-goal").textContent = "não foi possível carregar"; }
  renderHomeAlerts(alerts);
}

function expenseDueLabel(expense) {
  const today = localDate();
  const difference = Math.round((new Date(`${expense.occurred_on}T12:00:00`) - new Date(`${today}T12:00:00`)) / 86400000);
  if (expense.is_paid) return "paga";
  if (difference < 0) return `vencida há ${Math.abs(difference)} dia${difference === -1 ? "" : "s"}`;
  if (difference === 0) return "vence hoje";
  return `vence em ${difference} dia${difference === 1 ? "" : "s"}`;
}

function renderHomeAlerts(alerts) {
  $("home-alert-count").textContent = alerts.length ? `${alerts.length} pendência${alerts.length === 1 ? "" : "s"}` : "Operação em dia";
  $("home-alert-list").innerHTML = alerts.length ? alerts.map((alert) => alert.expenseId ? `<article class="home-alert ${alert.urgent ? "urgent" : ""}"><span>${alert.urgent ? "!" : escapeHtml(alert.icon)}</span><div><strong>${escapeHtml(alert.title)}</strong><small>${escapeHtml(alert.detail)}</small></div><button class="home-alert-pay" data-expense-paid="${alert.expenseId}" type="button">Confirmar paga</button></article>` : `<button class="home-alert" data-alert-view="${alert.view}" type="button"><span>${escapeHtml(alert.icon)}</span><div><strong>${escapeHtml(alert.title)}</strong><small>${escapeHtml(alert.detail)}</small></div><b>→</b></button>`).join("") : '<div class="home-alert-success"><span>✓</span><strong>Nenhuma pendência importante neste momento.</strong></div>';
}

async function fetchAgendaSnapshot(date, barberId = "all", includeAvailability = true) {
  const selectedBarbers = barberId === "all" ? state.barbers.filter((item) => item.is_active) : state.barbers.filter((item) => item.id === barberId);
  const results = await Promise.all(selectedBarbers.map(async (barber) => { const appointments = await request(`/businesses/${state.me.business_id}/barbers/${barber.id}/appointments?appointment_date=${date}`); const availability = includeAvailability ? await request(`/businesses/${state.me.business_id}/barbers/${barber.id}/availability?appointment_date=${date}`).catch(() => ({ slots: [] })) : { slots: [] }; return { appointments, free: availability.slots.length }; }));
  return { appointments: results.flatMap((item) => item.appointments).sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at)), free: results.reduce((total, item) => total + item.free, 0) };
}

async function loadAgenda() {
  const barberId = $("barber-filter").value; const date = $("date-filter").value;
  if (!barberId) { renderAppointments([]); return; }
  try {
    if (state.me.role === "barber") {
      const appointments = await request(`/auth/barber/appointments?appointment_date=${date}`);
      state.appointments = appointments; $("stat-total").textContent = appointments.length; $("stat-confirmed").textContent = appointments.filter((item) => item.status === "confirmed").length; $("stat-free").textContent = "—"; $("stat-revenue").textContent = formatMoney(appointments.filter((item) => item.status === "completed").reduce((total, item) => total + (item.price_cents || 0), 0)); renderAppointments(appointments); return;
    }
    const { appointments, free } = await fetchAgendaSnapshot(date, barberId);
    state.appointments = appointments; $("stat-total").textContent = appointments.length; $("stat-confirmed").textContent = appointments.filter((a) => a.status === "confirmed").length; $("stat-free").textContent = free; $("stat-revenue").textContent = formatMoney(appointments.filter((a) => a.status === "completed").reduce((total, a) => total + (a.price_cents || 0), 0)); renderAppointments(appointments);
  } catch (error) { showToast(error.message); }
}

function moveAgendaDate(days) {
  const [year, month, day] = $("date-filter").value.split("-").map(Number); const date = new Date(Date.UTC(year, month - 1, day + days)); $("date-filter").value = date.toISOString().slice(0, 10); loadAgenda();
}
function goToToday() { $("date-filter").value = localDate(); loadAgenda(); }

async function loadClosures() { try { const items = await request(`/businesses/${state.me.business_id}/closures`); $("closure-list").innerHTML = items.length ? items.map((item) => `<article class="closure-row"><div><strong>${item.closure_date.split("-").reverse().join("/")}</strong><span>${escapeHtml(item.reason)}</span></div><button data-closure-delete="${item.id}" type="button">Excluir</button></article>`).join("") : '<div class="empty">Nenhum dia de fechamento cadastrado.</div>'; } catch (error) { $("closure-error").textContent = error.message; } }
async function createClosure(event) { event.preventDefault(); $("closure-error").textContent = ""; try { await request(`/businesses/${state.me.business_id}/closures`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ closure_date: $("closure-date").value, reason: $("closure-reason").value.trim() }) }); $("closure-form").reset(); showToast("Dia de fechamento salvo com sucesso."); await loadClosures(); } catch (error) { $("closure-error").textContent = error.message.includes("already closed") ? "Esta data já está cadastrada." : error.message.includes("active appointments") ? "Existem atendimentos ativos nessa data. Reagende ou cancele esses clientes antes de fechar o dia." : error.message; } }
async function deleteClosure(id) { const confirmed = await confirmAction({ eyebrow: "FECHAMENTOS", title: "Excluir fechamento", detail: "Dia de fechamento selecionado", message: "A data voltará a ficar disponível para novos agendamentos.", confirmLabel: "Excluir fechamento", variant: "danger" }); if (!confirmed) return; try { await request(`/businesses/${state.me.business_id}/closures/${id}`, { method: "DELETE" }); showToast("Dia de fechamento removido."); await loadClosures(); } catch (error) { showToast(error.message); } }

function renderAppointments(items) {
  const query = $("agenda-search").value.trim().toLocaleLowerCase("pt-BR"); const queryDigits = query.replace(/\D/g, ""); const status = $("agenda-status").value;
  const visible = items.filter((appointment) => { const customer = state.customers.find((item) => item.id === appointment.customer_id); const barber = state.barbers.find((item) => item.id === appointment.barber_id); const customerName = appointment.customer_name || customer?.full_name || "Cliente"; const customerPhone = appointment.customer_phone || customer?.phone || ""; const barberName = barber?.full_name || state.barbers[0]?.full_name || "Profissional"; const matchesStatus = status === "all" || appointment.status === status; const matchesQuery = !query || customerName.toLocaleLowerCase("pt-BR").includes(query) || barberName.toLocaleLowerCase("pt-BR").includes(query) || (queryDigits && customerPhone.replace(/\D/g, "").includes(queryDigits)); return matchesStatus && matchesQuery; });
  $("schedule-count").textContent = visible.length === items.length ? `${items.length} atendimento${items.length === 1 ? "" : "s"}` : `${visible.length} de ${items.length} atendimentos`;
  if (!visible.length) { $("appointments").innerHTML = `<div class="empty">${items.length ? "Nenhum atendimento corresponde aos filtros." : "Nenhum atendimento nesta data."}</div>`; return; }
  $("appointments").innerHTML = visible.map((a) => { const customer = state.customers.find((c) => c.id === a.customer_id); const service = state.services.find((s) => s.id === a.service_id); const barber = state.barbers.find((b) => b.id === a.barber_id); const customerName = a.customer_name || customer?.full_name || "Cliente"; const serviceName = a.service_name || service?.name || a.notes || "Atendimento"; const barberName = barber?.full_name || state.barbers[0]?.full_name || "Profissional"; const active = ["scheduled", "confirmed"].includes(a.status); const ownerActions = state.me.role === "owner" && active ? `<button data-reschedule-id="${a.id}">Reagendar</button>` : ""; const activeActions = active ? `${ownerActions}<button data-reminder-id="${a.id}">WhatsApp</button><button data-complete-id="${a.id}">Concluir</button><button data-action="no-show" data-id="${a.id}">Não veio</button>${state.me.role === "owner" ? `<button data-action="cancel" data-id="${a.id}">Cancelar</button>` : ""}` : ""; return `<article class="appointment"><div class="time">${formatTime(a.starts_at)}</div><div class="person"><strong>${escapeHtml(customerName)}</strong><span>${escapeHtml(serviceName)} · ${escapeHtml(barberName)} · até ${formatTime(a.ends_at)}${a.price_cents != null ? ` · ${formatMoney(a.price_cents)}` : ""}</span></div><span class="badge ${a.status}">${statusLabel(a.status)}</span><div class="actions"><button data-detail-id="${a.id}">Detalhes</button>${a.status === "scheduled" ? `<button data-action="confirm" data-id="${a.id}">Confirmar</button>` : ""}${activeActions}</div></article>`; }).join("");
}

function openAppointmentDetail(id) {
  const appointment = state.appointments.find((item) => item.id === id); if (!appointment) return; const customer = state.customers.find((item) => item.id === appointment.customer_id); const barber = state.barbers.find((item) => item.id === appointment.barber_id); const service = state.services.find((item) => item.id === appointment.service_id);
  state.detailAppointmentId = id;
  const customerName = appointment.customer_name || customer?.full_name || "Cliente"; const customerPhone = appointment.customer_phone || customer?.phone || ""; const serviceName = appointment.service_name || service?.name || "Atendimento";
  $("appointment-detail-title").textContent = customerName; $("appointment-detail-subtitle").textContent = `${formatAppointmentDate(appointment.starts_at)} · ${formatTime(appointment.starts_at)} às ${formatTime(appointment.ends_at)}`;
  $("appointment-detail-content").innerHTML = `<dl><div><dt>Telefone</dt><dd>${escapeHtml(customerPhone || "Não informado")}</dd></div><div><dt>Profissional</dt><dd>${escapeHtml(barber?.full_name || state.barbers[0]?.full_name || "Não informado")}</dd></div><div><dt>Serviço</dt><dd>${escapeHtml(serviceName)}</dd></div><div><dt>Status</dt><dd><span class="badge ${appointment.status}">${statusLabel(appointment.status)}</span></dd></div><div><dt>Valor</dt><dd>${appointment.price_cents != null ? formatMoney(appointment.price_cents) : "Não informado"}</dd></div></dl>`;
  $("appointment-detail-notes").value = appointment.notes || ""; $("appointment-detail-error").textContent = "";
  $("appointment-detail-whatsapp").hidden = !customerPhone; $("appointment-detail-whatsapp").dataset.phone = customerPhone; $("appointment-detail-modal").hidden = false; document.body.classList.add("modal-open");
}
function closeAppointmentDetail() { $("appointment-detail-modal").hidden = true; document.body.classList.remove("modal-open"); }
async function saveAppointmentNotes() {
  const button = $("save-appointment-notes"); button.disabled = true; button.textContent = "Salvando..."; $("appointment-detail-error").textContent = "";
  try { const updated = await request(`/businesses/${state.me.business_id}/appointments/${state.detailAppointmentId}/notes`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ notes: $("appointment-detail-notes").value.trim() || null }) }); state.appointments = state.appointments.map((item) => item.id === updated.id ? updated : item); renderAppointments(state.appointments); closeAppointmentDetail(); showToast("Alterações salvas com sucesso."); } catch (error) { $("appointment-detail-error").textContent = error.message; } finally { button.disabled = false; button.textContent = "Salvar observações"; }
}

function formatMoney(cents) { return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(cents / 100); }

function renderReportRows(targetId, rows, total) {
  const target = $(targetId);
  if (!rows.length) { target.innerHTML = '<div class="empty">Nenhum recebimento no período.</div>'; return; }
  target.innerHTML = rows.map((row) => {
    const width = total > 0 ? Math.max(4, Math.round(row.total_cents / total * 100)) : 0;
    const commission = row.commission_cents == null ? "" : ` · comissão ${row.commission_percentage}%: ${formatMoney(row.commission_cents)}`;
    return `<article class="report-row"><div class="report-row-head"><strong>${row.label}</strong><span>${formatMoney(row.total_cents)}</span></div><div class="report-track"><i style="width:${width}%"></i></div><small>${row.appointments} atendimento${row.appointments === 1 ? "" : "s"}${commission}</small></article>`;
  }).join("");
}

function renderReportChange(targetId, current, previous) {
  const target = $(targetId); if (!previous && !current) { target.textContent = "Sem variação"; target.className = "report-change neutral"; return; }
  if (!previous) { target.textContent = "Novo no período"; target.className = "report-change positive"; return; }
  const change = Math.round((current - previous) / Math.abs(previous) * 100); target.textContent = `${change >= 0 ? "↑" : "↓"} ${Math.abs(change)}% vs. período anterior`; target.className = `report-change ${change > 0 ? "positive" : change < 0 ? "negative" : "neutral"}`;
}

function applyFinancialChartZoom(nextZoom, focusRatio = .5) {
  const viewport = $("financial-chart-viewport");
  const previousWidth = Math.max(viewport.scrollWidth, viewport.clientWidth), previousFocus = viewport.scrollLeft + viewport.clientWidth * focusRatio;
  state.financialChartZoom = Math.min(8, Math.max(1, Math.round(nextZoom * 2) / 2));
  renderFinancialChart(state.financialChartPoints);
  requestAnimationFrame(() => { const ratio = previousFocus / previousWidth; viewport.scrollLeft = Math.max(0, viewport.scrollWidth * ratio - viewport.clientWidth * focusRatio); });
}

function aggregateFinancialChartPoints(points) {
  if (state.financialChartPeriod === "day") return points;
  const groups = new Map();
  points.forEach((item) => {
    const current = new Date(`${item.date}T12:00:00Z`); let key;
    if (state.financialChartPeriod === "month") key = item.date.slice(0, 7) + "-01";
    else { const weekday = current.getUTCDay() || 7; current.setUTCDate(current.getUTCDate() - weekday + 1); key = current.toISOString().slice(0, 10); }
    const group = groups.get(key) || { date: key, appointments: 0, revenue_cents: 0, expense_cents: 0, result_cents: 0 };
    group.appointments += item.appointments; group.revenue_cents += item.revenue_cents; group.expense_cents += item.expense_cents; group.result_cents += item.result_cents; groups.set(key, group);
  });
  return [...groups.values()];
}

function financialChartDateLabel(value, short = false) {
  const date = new Date(`${value}T12:00:00Z`);
  if (state.financialChartPeriod === "month") return date.toLocaleDateString("pt-BR", { month: short ? "short" : "long", year: "numeric", timeZone: "UTC" });
  if (state.financialChartPeriod === "week" && !short) return `Semana de ${date.toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric", timeZone: "UTC" })}`;
  return date.toLocaleDateString("pt-BR", short ? { day: "2-digit", month: "2-digit", timeZone: "UTC" } : { day: "2-digit", month: "long", year: "numeric", timeZone: "UTC" });
}

function renderFinancialChart(points) {
  const target = $("financial-chart"); if (!points?.length) { target.innerHTML = '<div class="empty">Sem dados para o gráfico.</div>'; return; }
  state.financialChartPoints = points;
  points = aggregateFinancialChartPoints(points);
  const width = 920 * state.financialChartZoom, height = 340, left = 82, right = 28, top = 30, bottom = 58;
  target.style.width = `${state.financialChartZoom * 100}%`;
  $("chart-zoom-label").textContent = `${Math.round(state.financialChartZoom * 100)}%`;
  $("chart-zoom-out").disabled = state.financialChartZoom === 1;
  $("chart-zoom-in").disabled = state.financialChartZoom === 8;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const nice = (value) => { const power = 10 ** Math.floor(Math.log10(Math.max(value, 1))); return Math.ceil(value / power) * power; };
  const maximum = nice(Math.max(...points.flatMap((item) => [item.revenue_cents, item.expense_cents, Math.abs(item.result_cents)]), 1));
  const minimum = points.some((item) => item.result_cents < 0) ? -maximum : 0;
  const range = maximum - minimum, step = plotWidth / points.length, barWidth = Math.max(3, Math.min(18, step * .28));
  const x = (index) => left + step * index + step / 2;
  const y = (value) => top + (maximum - value) / range * plotHeight;
  const zeroY = y(0);
  const ticks = [minimum, minimum + range * .25, minimum + range * .5, minimum + range * .75, maximum];
  const grid = ticks.map((value) => `<line class="${Math.abs(value) < 1 ? "zero-line" : ""}" x1="${left}" y1="${y(value)}" x2="${width - right}" y2="${y(value)}"/><text x="${left - 12}" y="${y(value) + 4}" text-anchor="end">${formatMoney(Math.round(value))}</text>`).join("");
  const bars = points.map((item, index) => `<rect class="revenue-bar" x="${x(index) - barWidth - 2}" y="${y(item.revenue_cents)}" width="${barWidth}" height="${Math.max(0, zeroY - y(item.revenue_cents))}" rx="3"/><rect class="expense-bar" x="${x(index) + 2}" y="${y(item.expense_cents)}" width="${barWidth}" height="${Math.max(0, zeroY - y(item.expense_cents))}" rx="3"/>`).join("");
  const linePoints = points.map((item, index) => `${x(index)},${y(item.result_cents)}`).join(" ");
  const dots = points.map((item, index) => `<circle cx="${x(index)}" cy="${y(item.result_cents)}" r="4"/>`).join("");
  const hits = points.map((item, index) => `<rect data-chart-index="${index}" x="${left + step * index}" y="${top}" width="${step}" height="${plotHeight}"/>`).join("");
  const labelEvery = Math.max(1, Math.ceil(points.length / (9 * state.financialChartZoom)));
  const labels = points.map((item, index) => index % labelEvery === 0 || index === points.length - 1 ? `<text x="${x(index)}" y="${height - 23}" text-anchor="middle">${financialChartDateLabel(item.date, true)}</text>` : "").join("");
  target.innerHTML = `<div class="chart-tooltip" hidden></div><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Comparativo diário de receitas, despesas e resultado líquido"><text class="axis-title" x="${left}" y="15">Valores em reais</text><g class="chart-grid">${grid}</g><g class="chart-bars">${bars}</g><polyline class="chart-line" points="${linePoints}"/><g class="chart-dots">${dots}</g><line class="chart-hover-guide" x1="0" y1="${top}" x2="0" y2="${top + plotHeight}" hidden/><g class="chart-labels">${labels}</g><g class="chart-hit-areas">${hits}</g></svg>`;
  const tooltip = target.querySelector(".chart-tooltip"), guide = target.querySelector(".chart-hover-guide");
  target.querySelectorAll("[data-chart-index]").forEach((area) => { area.addEventListener("pointerenter", () => { const index = Number(area.dataset.chartIndex), item = points[index], center = x(index) / width * 100; guide.setAttribute("x1", x(index)); guide.setAttribute("x2", x(index)); guide.hidden = false; tooltip.innerHTML = `<strong>${financialChartDateLabel(item.date)}</strong><span>Receitas <b>${formatMoney(item.revenue_cents)}</b></span><span>Despesas <b>${formatMoney(item.expense_cents)}</b></span><span>Resultado <b>${formatMoney(item.result_cents)}</b></span><span>Atendimentos <b>${item.appointments}</b></span>`; tooltip.style.left = `${Math.min(84, Math.max(16, center))}%`; tooltip.hidden = false; }); area.addEventListener("pointerleave", () => { guide.hidden = true; tooltip.hidden = true; }); });
}

async function loadFinancialChartPeriod() {
  const dateFrom = $("chart-date-from").value, dateTo = $("chart-date-to").value, button = $("refresh-financial-chart");
  if (!dateFrom || !dateTo || dateTo < dateFrom) { showToast("Escolha um período válido para o gráfico."); return; }
  button.disabled = true; button.textContent = "Atualizando...";
  try {
    const report = await request(`/businesses/${state.me.business_id}/reports/financial?date_from=${dateFrom}&date_to=${dateTo}`);
    state.financialChartZoom = 1; $("financial-chart-viewport").scrollLeft = 0; renderFinancialChart(report.daily);
    const format = (value) => new Date(`${value}T12:00:00`).toLocaleDateString("pt-BR");
    $("chart-date-label").textContent = `Exibindo ${format(dateFrom)} até ${format(dateTo)}. Somente o gráfico foi atualizado.`;
    return report;
  } catch (error) { showToast(error.message); }
  finally { button.disabled = false; button.textContent = "Atualizar gráfico"; }
  return null;
}

function renderGoalMonthAnalysis(report, monthValue) {
  if (!report) return;
  const target = $("goal-month-analysis"), goal = state.business?.monthly_revenue_goal_cents || 0, revenue = report.total_revenue_cents, result = report.final_result_cents;
  const goalDifference = revenue - goal, margin = revenue ? Math.round(result / revenue * 100) : 0, commissionRate = revenue ? Math.round(report.total_commission_cents / revenue * 100) : 0, expenseRate = revenue ? Math.round(report.total_expenses_cents / revenue * 100) : 0;
  const monthName = new Date(`${monthValue}-01T12:00:00Z`).toLocaleDateString("pt-BR", { month: "long", year: "numeric", timeZone: "UTC" });
  const observations = [];
  observations.push(goalDifference >= 0 ? `A meta foi superada em ${formatMoney(goalDifference)}.` : `O faturamento ficou ${formatMoney(Math.abs(goalDifference))} abaixo da meta.`);
  observations.push(result >= 0 ? `A operação encerrou o mês com resultado positivo de ${formatMoney(result)} e margem de ${margin}%.` : `A operação encerrou o mês no vermelho em ${formatMoney(Math.abs(result))}, com margem de ${margin}%.`);
  observations.push(`Comissões consumiram ${commissionRate}% do faturamento e as despesas operacionais representaram ${expenseRate}%.`);
  const topBarber = report.by_barber[0], topService = report.by_service[0];
  if (topBarber) observations.push(`${topBarber.label} liderou a equipe com ${topBarber.appointments} atendimentos e ${formatMoney(topBarber.total_cents)} em faturamento.`);
  if (topService) observations.push(`${topService.label} foi o serviço de maior faturamento, somando ${topService.appointments} realizações e ${formatMoney(topService.total_cents)}.`);
  const recommendations = [];
  if (goalDifference < 0) recommendations.push("Reforçar ocupação da agenda e ações de retorno dos clientes para elevar o faturamento.");
  if (expenseRate > 40) recommendations.push("Revisar despesas do mês, priorizando itens variáveis e compras de produtos.");
  if (report.attendance_rate_percent < 90) recommendations.push("Reduzir faltas com confirmações e lembretes antecipados aos clientes.");
  if (margin < 15) recommendations.push("Reavaliar preços, descontos e custos para recuperar a margem operacional.");
  if (topBarber && revenue && topBarber.total_cents / revenue > .55) recommendations.push("Reduzir a concentração de faturamento em um único profissional, fortalecendo a ocupação do restante da equipe.");
  if (!recommendations.length) recommendations.push("Manter o padrão operacional e usar este mês como referência para os próximos períodos.");
  const status = result >= 0 ? "Mês no verde" : "Mês no vermelho";
  const barberRows = report.by_barber.length ? report.by_barber.map((item) => `<tr><td>${escapeHtml(item.label)}</td><td>${item.appointments}</td><td>${formatMoney(item.total_cents)}</td><td>${item.commission_percentage ?? 0}% · ${formatMoney(item.commission_cents || 0)}</td></tr>`).join("") : '<tr><td colspan="4">Nenhum atendimento concluído.</td></tr>';
  const serviceRows = report.by_service.length ? report.by_service.map((item) => `<tr><td>${escapeHtml(item.label)}</td><td>${item.appointments}</td><td>${formatMoney(item.total_cents)}</td><td>${item.appointments ? formatMoney(Math.round(item.total_cents / item.appointments)) : formatMoney(0)}</td></tr>`).join("") : '<tr><td colspan="4">Nenhum serviço concluído.</td></tr>';
  const expenseCategories = new Map(); report.expenses.forEach((item) => { const current = expenseCategories.get(item.category) || { count: 0, total: 0, paid: 0, pending: 0 }; current.count += 1; current.total += item.amount_cents; current[item.is_paid ? "paid" : "pending"] += item.amount_cents; expenseCategories.set(item.category, current); });
  const expenseRows = expenseCategories.size ? [...expenseCategories.entries()].sort((first, second) => second[1].total - first[1].total).map(([category, item]) => `<tr><td>${expenseLabels[category] || escapeHtml(category)}</td><td>${item.count}</td><td>${formatMoney(item.total)}</td><td>${formatMoney(item.paid)}</td><td>${formatMoney(item.pending)}</td></tr>`).join("") : '<tr><td colspan="5">Nenhuma despesa registrada.</td></tr>';
  target.className = `goal-month-analysis ${result >= 0 ? "positive" : "negative"}`; target.hidden = false;
  target.innerHTML = `<div class="goal-analysis-head"><div><p class="eyebrow">ANÁLISE DO MÊS SELECIONADO</p><h3>${monthName}</h3><span>${status}</span></div><div class="goal-analysis-result"><strong>${result >= 0 ? "+" : "−"}${formatMoney(Math.abs(result))}</strong><div><button id="copy-goal-analysis" class="secondary compact" type="button">Copiar análise</button><button id="print-goal-analysis" class="primary compact" type="button">Imprimir / PDF</button></div></div></div><div class="goal-analysis-kpis"><article><span>FATURAMENTO</span><strong>${formatMoney(revenue)}</strong><small>${goal ? `${Math.round(revenue / goal * 100)}% da meta` : "meta não definida"}</small></article><article><span>COMISSÕES</span><strong>${formatMoney(report.total_commission_cents)}</strong><small>${commissionRate}% do faturamento</small></article><article><span>DESPESAS</span><strong>${formatMoney(report.total_expenses_cents)}</strong><small>${expenseRate}% do faturamento</small></article><article><span>MARGEM FINAL</span><strong>${margin}%</strong><small>${formatMoney(result)} de resultado</small></article><article><span>ATENDIMENTOS</span><strong>${report.completed}</strong><small>${report.attendance_rate_percent}% de comparecimento</small></article><article><span>TICKET MÉDIO</span><strong>${formatMoney(report.average_ticket_cents)}</strong><small>por atendimento concluído</small></article></div><div class="goal-data-analysis"><section><h4>Atendimentos por profissional</h4><div><table><thead><tr><th>Profissional</th><th>Cortes</th><th>Faturamento</th><th>Comissão</th></tr></thead><tbody>${barberRows}</tbody></table></div></section><section><h4>Desempenho por serviço</h4><div><table><thead><tr><th>Serviço</th><th>Quantidade</th><th>Faturamento</th><th>Ticket médio</th></tr></thead><tbody>${serviceRows}</tbody></table></div></section><section class="goal-expense-analysis"><h4>Despesas por categoria</h4><div><table><thead><tr><th>Categoria</th><th>Lançamentos</th><th>Total</th><th>Pago</th><th>Pendente</th></tr></thead><tbody>${expenseRows}</tbody></table></div></section></div><div class="goal-analysis-report"><h4>Parecer financeiro e operacional</h4>${observations.map((item) => `<p>${item}</p>`).join("")}<h4>Recomendações</h4><ol>${recommendations.map((item) => `<li>${item}</li>`).join("")}</ol></div>`;
}

function printGoalMonthAnalysis() {
  const source = $("goal-month-analysis"); if (source.hidden) return;
  const printable = source.cloneNode(true); printable.querySelectorAll("button").forEach((button) => button.remove());
  const printWindow = window.open("", "_blank"); if (!printWindow) { showToast("Permita a abertura de janelas para gerar o PDF."); return; }
  printWindow.opener = null; const generatedAt = new Date().toLocaleString("pt-BR", { timeZone: state.business?.timezone || "America/Sao_Paulo" });
  printWindow.document.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Análise mensal — Osiris</title><style>@page{size:A4;margin:13mm}*{box-sizing:border-box}body{margin:0;color:#172019;font:11px Arial,sans-serif}.report-header{display:flex;justify-content:space-between;align-items:end;padding-bottom:13px;margin-bottom:16px;border-bottom:3px solid #78b82a}.brand{font-size:25px;font-weight:900}.brand i{color:#78b82a;font-style:normal}.report-header p,.meta{color:#657168}.meta{text-align:right}.goal-month-analysis{padding:0}.goal-analysis-head{display:flex;justify-content:space-between;align-items:end}.eyebrow{color:#598e1d;font-size:8px;font-weight:800;letter-spacing:.12em}.goal-analysis-head h3{font-size:22px;text-transform:capitalize;margin:3px 0}.goal-analysis-head span{color:#657168}.goal-analysis-result>strong{font-size:24px;color:#598e1d}.goal-analysis-kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:14px}.goal-analysis-kpis article{padding:10px;border:1px solid #d9ded9}.goal-analysis-kpis span{font-size:8px;font-weight:800;color:#657168}.goal-analysis-kpis strong{display:block;font-size:16px;margin:5px 0}.goal-analysis-kpis small{color:#657168}.goal-data-analysis{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:11px}.goal-data-analysis section{border:1px solid #d9ded9}.goal-data-analysis .goal-expense-analysis{grid-column:1/-1}.goal-data-analysis h4{margin:0;padding:9px;color:#598e1d;text-transform:uppercase;font-size:8px;border-bottom:1px solid #d9ded9}.goal-data-analysis table{width:100%;border-collapse:collapse}.goal-data-analysis th,.goal-data-analysis td{padding:6px;text-align:right;border-bottom:1px solid #e7eae7;font-size:8px}.goal-data-analysis th:first-child,.goal-data-analysis td:first-child{text-align:left}.goal-data-analysis th{color:#657168}.goal-analysis-report{margin-top:11px;padding:14px;background:#f2f4ef;border-left:4px solid #78b82a}.goal-analysis-report h4{margin:0 0 7px;color:#598e1d;text-transform:uppercase;font-size:9px}.goal-analysis-report h4:not(:first-child){margin-top:12px}.goal-analysis-report p,.goal-analysis-report li{line-height:1.5;color:#3f4941}.goal-analysis-report p{margin:4px 0}.goal-analysis-report ol{margin-bottom:0;padding-left:18px}.footer{margin-top:12px;padding-top:7px;border-top:1px solid #d9ded9;text-align:center;color:#7a847c;font-size:8px}@media print{article,section,tr{break-inside:avoid}}</style></head><body><header class="report-header"><div><div class="brand">osiris<i>.</i></div><p>${escapeHtml(state.business?.name || "Gestão da barbearia")}</p></div><div class="meta">Análise financeira e operacional mensal<br>Gerado em ${escapeHtml(generatedAt)}</div></header>${printable.outerHTML}<footer class="footer">Projeto Osiris · Relatório baseado nos dados registrados no sistema.</footer><script>window.addEventListener("load",()=>setTimeout(()=>window.print(),250));<\/script></body></html>`);
  printWindow.document.close();
}

async function loadFinancial() {
  const dateFrom = $("report-from").value; const dateTo = $("report-to").value;
  const errorBox = $("report-error"); errorBox.hidden = true;
  if (!dateFrom || !dateTo || dateTo < dateFrom) { errorBox.textContent = "Escolha um período válido."; errorBox.hidden = false; return; }
  $("refresh-report").disabled = true;
  try {
    const start = new Date(`${dateFrom}T00:00:00Z`), end = new Date(`${dateTo}T00:00:00Z`), durationDays = Math.round((end - start) / 86400000) + 1; const previousEnd = new Date(start.getTime() - 86400000), previousStart = new Date(previousEnd.getTime() - (durationDays - 1) * 86400000); const previousFrom = previousStart.toISOString().slice(0, 10), previousTo = previousEnd.toISOString().slice(0, 10);
    const [report, previous] = await Promise.all([request(`/businesses/${state.me.business_id}/reports/financial?date_from=${dateFrom}&date_to=${dateTo}`), request(`/businesses/${state.me.business_id}/reports/financial?date_from=${previousFrom}&date_to=${previousTo}`)]);
    state.financialReport = report; $("export-report").disabled = false;
    $("report-revenue").textContent = formatMoney(report.total_revenue_cents);
    $("report-commission").textContent = formatMoney(report.total_commission_cents);
    $("report-net").textContent = formatMoney(report.net_revenue_cents);
    $("report-expenses-total").textContent = formatMoney(report.total_expenses_cents);
    $("report-result").textContent = formatMoney(report.final_result_cents);
    $("report-average-ticket").textContent = formatMoney(report.average_ticket_cents);
    $("report-attendance-rate").textContent = `${report.attendance_rate_percent}%`;
    renderReportChange("report-revenue-change", report.total_revenue_cents, previous.total_revenue_cents);
    renderReportChange("report-result-change", report.final_result_cents, previous.final_result_cents);
    const attendanceTarget = $("report-attendance-change"); const attendanceDifference = report.attendance_rate_percent - previous.attendance_rate_percent; attendanceTarget.textContent = `${attendanceDifference >= 0 ? "↑" : "↓"} ${Math.abs(attendanceDifference)} pontos vs. período anterior`; attendanceTarget.className = `report-change ${attendanceDifference > 0 ? "positive" : attendanceDifference < 0 ? "negative" : "neutral"}`;
    loadFinancialChartPeriod();
    renderRevenueGoal(report.total_revenue_cents);
    loadRevenueGoalHistory();
    $("report-completed").textContent = report.completed;
    $("report-cancelled").textContent = report.cancelled;
    $("report-no-show").textContent = report.no_show;
    renderReportRows("report-barbers", report.by_barber, report.total_revenue_cents);
    renderReportRows("report-services", report.by_service, report.total_revenue_cents);
    renderReportRows("report-payments", report.by_payment_method, report.total_revenue_cents);
    loadExpensePeriod();
  } catch (error) { errorBox.textContent = error.message; errorBox.hidden = false; }
  finally { $("refresh-report").disabled = false; }
}

const expenseLabels = { rent: "Aluguel", supplies: "Materiais", utilities: "Contas", marketing: "Marketing", taxes: "Impostos", other: "Outros" };
function renderExpenseSummary(items) {
  const paid = items.filter((item) => item.is_paid), pending = items.filter((item) => !item.is_paid), fixed = items.filter((item) => item.is_fixed);
  const overdue = pending.filter((item) => item.occurred_on < localDate());
  $("expense-paid-total").textContent = formatMoney(paid.reduce((total, item) => total + item.amount_cents, 0));
  $("expense-paid-count").textContent = `${paid.length} despesa${paid.length === 1 ? "" : "s"}`;
  $("expense-pending-total").textContent = formatMoney(pending.reduce((total, item) => total + item.amount_cents, 0));
  $("expense-pending-count").textContent = `${pending.length} despesa${pending.length === 1 ? "" : "s"}`;
  $("expense-overdue-total").textContent = formatMoney(overdue.reduce((total, item) => total + item.amount_cents, 0));
  $("expense-overdue-count").textContent = `${overdue.length} despesa${overdue.length === 1 ? "" : "s"}`;
  $("expense-fixed-total").textContent = formatMoney(fixed.reduce((total, item) => total + item.amount_cents, 0));
  $("expense-fixed-count").textContent = `${fixed.length} despesa${fixed.length === 1 ? "" : "s"}`;
}

async function loadExpensePeriod() {
  const dateFrom = $("expense-summary-from").value, dateTo = $("expense-summary-to").value, button = $("refresh-expense-summary");
  if (!dateFrom || !dateTo || dateTo < dateFrom) { showToast("Escolha um período válido para os cartões."); return; }
  button.disabled = true;
  try {
    const items = await request(`/businesses/${state.me.business_id}/expenses?date_from=${dateFrom}&date_to=${dateTo}`);
    state.expensePeriodItems = items;
    renderExpenseSummary(items);
    renderExpenses(items);
    const format = (value) => new Date(`${value}T12:00:00`).toLocaleDateString("pt-BR");
    $("expense-summary-period").textContent = `Cartões e lista de ${format(dateFrom)} até ${format(dateTo)}. Os demais relatórios não foram alterados.`;
  } catch (error) { showToast(error.message); }
  finally { button.disabled = false; }
}

function expenseMonthRange(value) {
  const [year, month] = value.split("-").map(Number), lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return { from: `${value}-01`, to: `${value}-${String(lastDay).padStart(2, "0")}` };
}

function expenseMonthSummary(items) {
  return { total: items.reduce((sum, item) => sum + item.amount_cents, 0), paid: items.filter((item) => item.is_paid).reduce((sum, item) => sum + item.amount_cents, 0), pending: items.filter((item) => !item.is_paid).reduce((sum, item) => sum + item.amount_cents, 0), fixed: items.filter((item) => item.is_fixed).reduce((sum, item) => sum + item.amount_cents, 0), overdue: items.filter((item) => !item.is_paid && item.occurred_on < localDate()).reduce((sum, item) => sum + item.amount_cents, 0), count: items.length };
}

function expenseMonthsBetween(start, end) {
  const [startYear, startMonth] = start.split("-").map(Number), [endYear, endMonth] = end.split("-").map(Number), months = [];
  const cursor = new Date(Date.UTC(startYear, startMonth - 1, 1)), limit = new Date(Date.UTC(endYear, endMonth - 1, 1));
  while (cursor <= limit && months.length < 37) { months.push(cursor.toISOString().slice(0, 7)); cursor.setUTCMonth(cursor.getUTCMonth() + 1); }
  return months;
}

const expenseMonthLabel = (value, short = false) => new Date(`${value}-01T12:00:00`).toLocaleDateString("pt-BR", { month: short ? "short" : "long", year: "numeric" });

async function compareExpenseMonths() {
  const monthA = $("comparison-month-a").value, monthB = $("comparison-month-b").value, button = $("compare-expense-months");
  if (!monthA || !monthB || monthB < monthA) { showToast("Escolha um intervalo de meses válido."); return; }
  const months = expenseMonthsBetween(monthA, monthB);
  if (months.length > 36) { showToast("Selecione um período de até 36 meses."); return; }
  button.disabled = true;
  button.textContent = "Analisando...";
  try {
    const itemGroups = await Promise.all(months.map((month) => { const range = expenseMonthRange(month); return request(`/businesses/${state.me.business_id}/expenses?date_from=${range.from}&date_to=${range.to}`); }));
    const data = months.map((month, index) => ({ month, ...expenseMonthSummary(itemGroups[index]) }));
    const total = data.reduce((sum, item) => sum + item.total, 0), paid = data.reduce((sum, item) => sum + item.paid, 0), pending = data.reduce((sum, item) => sum + item.pending, 0), fixed = data.reduce((sum, item) => sum + item.fixed, 0), overdue = data.reduce((sum, item) => sum + item.overdue, 0), count = data.reduce((sum, item) => sum + item.count, 0), average = Math.round(total / data.length);
    const highest = data.reduce((best, item) => item.total > best.total ? item : best), lowest = data.reduce((best, item) => item.total < best.total ? item : best);
    const first = data[0], last = data[data.length - 1], trend = first.total ? Math.round((last.total - first.total) / first.total * 100) : null;
    const changes = data.slice(1).map((item, index) => ({ month: item.month, amount: item.total - data[index].total, percent: data[index].total ? Math.round((item.total - data[index].total) / data[index].total * 100) : null }));
    const largestChange = changes.length ? changes.reduce((best, item) => Math.abs(item.amount) > Math.abs(best.amount) ? item : best) : null;
    const paidRate = total ? Math.round(paid / total * 100) : 0, pendingRate = total ? Math.round(pending / total * 100) : 0, fixedRate = total ? Math.round(fixed / total * 100) : 0;
    const trendText = trend === null ? "não pode ser calculada porque o primeiro mês não possui despesas" : trend === 0 ? "permaneceu estável entre o primeiro e o último mês" : `${trend > 0 ? "aumentou" : "diminuiu"} ${Math.abs(trend)}% entre o primeiro e o último mês`;
    const assessment = [];
    if (pendingRate >= 30) assessment.push(`O volume pendente representa ${pendingRate}% das despesas, nível que exige atenção ao fluxo de caixa.`); else assessment.push(`O controle de pagamentos está em nível ${pendingRate <= 10 ? "saudável" : "moderado"}, com ${pendingRate}% ainda pendente.`);
    if (fixedRate >= 60) assessment.push(`Os custos fixos correspondem a ${fixedRate}% do total, indicando uma estrutura pouco flexível para ajustes rápidos.`); else assessment.push(`Os custos fixos representam ${fixedRate}% do total, preservando margem para gestão dos gastos variáveis.`);
    if (overdue > 0) assessment.push(`Há ${formatMoney(overdue)} em despesas vencidas dentro do período analisado.`); else assessment.push("Não há valores vencidos no período analisado.");
    const recommendations = [];
    if (pendingRate >= 20) recommendations.push("Priorizar a quitação e negociação das despesas pendentes, começando pelas vencidas.");
    if (fixedRate >= 60) recommendations.push("Revisar contratos e despesas recorrentes para reduzir o comprometimento fixo mensal.");
    if (trend !== null && trend > 10) recommendations.push("Investigar os itens responsáveis pelo crescimento dos gastos e estabelecer limites por categoria.");
    if (!recommendations.length) recommendations.push("Manter o acompanhamento mensal e utilizar o menor mês como referência de eficiência operacional.");
    recommendations.push("Comparar esta evolução com faturamento e número de atendimentos antes de tomar decisões de corte.");
    const reportTitle = `Análise de despesas — ${expenseMonthLabel(monthA)} a ${expenseMonthLabel(monthB)}`;
    const overview = `No período de ${data.length} ${data.length === 1 ? "mês" : "meses"}, foram registrados ${count} lançamentos, totalizando ${formatMoney(total)}, com média mensal de ${formatMoney(average)}. O maior volume ocorreu em ${expenseMonthLabel(highest.month)}, com ${formatMoney(highest.total)}, e o menor em ${expenseMonthLabel(lowest.month)}, com ${formatMoney(lowest.total)}.`;
    const evolution = `A despesa mensal ${trendText}. ${largestChange ? `A variação mais intensa aconteceu em ${expenseMonthLabel(largestChange.month)}, com ${largestChange.amount >= 0 ? "aumento" : "redução"} de ${formatMoney(Math.abs(largestChange.amount))}${largestChange.percent === null ? "" : ` (${Math.abs(largestChange.percent)}%)`} em relação ao mês anterior.` : "O intervalo possui apenas um mês, portanto não há variação mensal para comparar."}`;
    const composition = `Do total analisado, ${formatMoney(paid)} (${paidRate}%) está pago, ${formatMoney(pending)} (${pendingRate}%) permanece pendente e ${formatMoney(fixed)} (${fixedRate}%) corresponde a custos fixos.`;
    state.expenseAnalysisText = `${reportTitle}\n\nRESUMO EXECUTIVO\n${overview}\n\nEVOLUÇÃO\n${evolution}\n\nCOMPOSIÇÃO E RISCO\n${composition} ${assessment.join(" ")}\n\nRECOMENDAÇÕES\n${recommendations.map((item, index) => `${index + 1}. ${item}`).join("\n")}`;
    const maxTotal = Math.max(...data.map((item) => item.total), 1);
    const bars = data.map((item) => `<div class="analysis-bar-column" title="${expenseMonthLabel(item.month)}: ${formatMoney(item.total)}"><div class="analysis-bar-value">${formatMoney(item.total)}</div><div class="analysis-bar-track"><i style="height:${Math.max(3, Math.round(item.total / maxTotal * 100))}%"></i></div><span>${expenseMonthLabel(item.month, true)}</span></div>`).join("");
    const rows = data.map((item, index) => { const change = index ? item.total - data[index - 1].total : null; return `<tr><td>${expenseMonthLabel(item.month)}</td><td>${formatMoney(item.total)}</td><td>${formatMoney(item.paid)}</td><td>${formatMoney(item.pending)}</td><td>${formatMoney(item.fixed)}</td><td class="${change > 0 ? "negative" : change < 0 ? "positive" : ""}">${change === null ? "—" : `${change > 0 ? "+" : "−"}${formatMoney(Math.abs(change))}`}</td></tr>`; }).join("");
    $("expense-comparison-results").className = "expense-analysis-results";
    $("expense-comparison-results").innerHTML = `<div class="analysis-kpis"><article><span>TOTAL DO PERÍODO</span><strong>${formatMoney(total)}</strong><small>${count} lançamentos</small></article><article><span>MÉDIA MENSAL</span><strong>${formatMoney(average)}</strong><small>${data.length} ${data.length === 1 ? "mês analisado" : "meses analisados"}</small></article><article><span>MAIOR MÊS</span><strong>${formatMoney(highest.total)}</strong><small>${expenseMonthLabel(highest.month)}</small></article><article><span>VALORES PENDENTES</span><strong>${formatMoney(pending)}</strong><small>${pendingRate}% do total</small></article></div><section class="analysis-chart"><h4>Evolução mensal das despesas</h4><div class="analysis-bars">${bars}</div></section><div class="analysis-table-wrap"><table class="analysis-table"><thead><tr><th>Mês</th><th>Total</th><th>Pago</th><th>Pendente</th><th>Fixo</th><th>Variação</th></tr></thead><tbody>${rows}</tbody></table></div><section class="written-analysis"><div class="written-analysis-head"><div><p class="eyebrow">PARECER DO ANALISTA</p><h4>${reportTitle}</h4></div><div class="written-analysis-actions"><button id="copy-expense-analysis" class="secondary compact" type="button">Copiar relatório</button><button id="print-expense-analysis" class="primary compact" type="button">Imprimir / PDF</button></div></div><h5>Resumo executivo</h5><p>${overview}</p><h5>Evolução dos gastos</h5><p>${evolution}</p><h5>Composição e riscos</h5><p>${composition} ${assessment.join(" ")}</p><h5>Recomendações</h5><ol>${recommendations.map((item) => `<li>${item}</li>`).join("")}</ol></section>`;
  } catch (error) { showToast(error.message); }
  finally { button.disabled = false; button.textContent = "Analisar período"; }
}

function printExpenseAnalysis() {
  const source = $("expense-comparison-results");
  if (!state.expenseAnalysisText || !source.classList.contains("expense-analysis-results")) return;
  const printable = source.cloneNode(true); printable.querySelectorAll("button").forEach((button) => button.remove());
  const printWindow = window.open("", "_blank");
  if (!printWindow) { showToast("Permita a abertura de janelas para gerar o PDF."); return; }
  printWindow.opener = null;
  const generatedAt = new Date().toLocaleString("pt-BR", { timeZone: state.business?.timezone || "America/Sao_Paulo" });
  printWindow.document.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Relatório de despesas — Osiris</title><style>@page{size:A4;margin:14mm}*{box-sizing:border-box}body{margin:0;color:#172019;font-family:Arial,sans-serif;font-size:11px}.report-header{display:flex;justify-content:space-between;align-items:end;border-bottom:3px solid #78b82a;padding-bottom:14px;margin-bottom:18px}.brand{font-size:25px;font-weight:900}.brand i{color:#78b82a;font-style:normal}.report-header p{margin:4px 0 0;color:#657168}.meta{text-align:right;color:#657168}.analysis-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.analysis-kpis article{padding:12px;border:1px solid #d9ded9;border-top:3px solid #78b82a}.analysis-kpis span{display:block;font-size:8px;font-weight:800;letter-spacing:.08em;color:#657168}.analysis-kpis strong{display:block;font-size:17px;margin:6px 0}.analysis-kpis small{color:#657168}.analysis-chart{margin-top:14px;padding:14px;border:1px solid #d9ded9;break-inside:avoid}.analysis-chart h4{margin:0 0 10px}.analysis-bars{height:180px;display:flex;align-items:stretch;gap:5px}.analysis-bar-column{min-width:28px;flex:1;display:grid;grid-template-rows:15px 1fr 25px;gap:4px;text-align:center}.analysis-bar-value{font-size:7px;color:#657168}.analysis-bar-track{display:flex;align-items:end;justify-content:center;border-bottom:1px solid #bdc6bd}.analysis-bar-track i{display:block;width:60%;background:#78b82a}.analysis-bar-column>span{font-size:7px;color:#657168}.analysis-table-wrap{margin-top:14px}.analysis-table{width:100%;border-collapse:collapse}.analysis-table th,.analysis-table td{padding:7px;text-align:right;border-bottom:1px solid #d9ded9}.analysis-table th:first-child,.analysis-table td:first-child{text-align:left}.analysis-table th{font-size:8px;color:#657168}.positive{color:#4d7c18}.negative{color:#bd3e38}.written-analysis{margin-top:16px;padding:18px;background:#f2f4ef;border-left:4px solid #78b82a}.written-analysis-head{display:block}.eyebrow{color:#598e1d;font-size:8px;font-weight:800;letter-spacing:.12em}.written-analysis h4{font-size:17px;margin:4px 0 14px}.written-analysis h5{margin:14px 0 4px;text-transform:uppercase;font-size:9px}.written-analysis p,.written-analysis li{line-height:1.55;color:#3f4941}.written-analysis ol{margin-bottom:0;padding-left:18px}.print-footer{margin-top:14px;padding-top:8px;border-top:1px solid #d9ded9;color:#7a847c;font-size:8px;text-align:center}@media print{.analysis-table tr,.written-analysis{break-inside:avoid}}</style></head><body><header class="report-header"><div><div class="brand">osiris<i>.</i></div><p>${escapeHtml(state.business?.name || "Gestão da barbearia")}</p></div><div class="meta">Relatório financeiro profissional<br>Gerado em ${escapeHtml(generatedAt)}</div></header>${printable.outerHTML}<footer class="print-footer">Projeto Osiris · Relatório gerado com base nos lançamentos cadastrados no sistema.</footer><script>window.addEventListener("load",()=>setTimeout(()=>window.print(),250));<\/script></body></html>`);
  printWindow.document.close();
}

function renderExpenses(items) {
  const filter = $("expense-filter").value;
  document.querySelectorAll("[data-expense-summary-filter]").forEach((card) => card.classList.toggle("active", card.dataset.expenseSummaryFilter === filter));
  const today = localDate();
  const expensePriority = (item) => item.is_paid ? 2 : item.occurred_on < today ? 0 : 1;
  const visible = items
    .filter((item) => filter === "all" || filter === "pending" && !item.is_paid || filter === "due" && !item.is_paid && item.occurred_on >= today || filter === "overdue" && !item.is_paid && item.occurred_on < today || filter === "paid" && item.is_paid || filter === "fixed" && item.is_fixed || filter === "variable" && !item.is_fixed)
    .sort((first, second) => expensePriority(first) - expensePriority(second) || (first.is_paid ? second.occurred_on.localeCompare(first.occurred_on) : first.occurred_on.localeCompare(second.occurred_on)));
  $("expense-count").textContent = visible.length === items.length ? `${items.length} despesa${items.length === 1 ? "" : "s"}` : `${visible.length} de ${items.length} despesas`;
  if (!visible.length) { $("expenses").innerHTML = '<div class="empty">Nenhuma despesa encontrada neste filtro.</div>'; return; }
  $("expenses").innerHTML = visible.map((item) => { const overdue = !item.is_paid && item.occurred_on < today; return `<article class="expense-row ${overdue ? "overdue" : ""}"><div><strong>${escapeHtml(item.description)}${item.is_fixed ? ' <em class="fixed-expense-badge">Fixa</em>' : ""}</strong><span>${expenseLabels[item.category] || escapeHtml(item.category)} · ${new Date(`${item.occurred_on}T12:00:00`).toLocaleDateString("pt-BR")} · <em class="expense-payment-status ${item.is_paid ? "paid" : overdue ? "overdue" : "pending"}">${item.is_paid ? "Paga" : overdue ? "Vencida" : "Pendente"}</em> · ${expenseDueLabel(item)}</span></div><strong>${formatMoney(item.amount_cents)}</strong><div class="actions">${item.is_paid ? `<button class="expense-pending-button" data-expense-pending="${item.id}" type="button">Marcar pendente</button>` : `<button class="expense-paid-button" data-expense-paid="${item.id}" type="button">Confirmar pagamento</button>`}<button data-expense-edit="${item.id}" type="button">Editar</button><button class="expense-delete" data-expense-id="${item.id}" type="button">Excluir</button></div></article>`; }).join("");
}

async function markExpensePaid(id) {
  const expense = [...state.expensePeriodItems, ...state.homeExpenses].find((item) => item.id === id);
  const confirmed = await confirmAction({
    eyebrow: "CONTROLE FINANCEIRO",
    title: "Confirmar pagamento",
    detail: expense ? `${expense.description} · ${formatMoney(expense.amount_cents)}` : "Despesa selecionada",
    message: "Esta despesa será registrada como paga e os indicadores financeiros serão atualizados.",
    confirmLabel: "Confirmar como paga",
  });
  if (!confirmed) return;
  try {
    await request(`/businesses/${state.me.business_id}/expenses/${id}/paid`, { method: "PATCH" });
    showToast("Pagamento da despesa confirmado.");
    await Promise.all([loadFinancial(), loadHome()]);
  } catch (error) { showToast(error.message); }
}

async function markExpensePending(id) {
  const expense = [...state.expensePeriodItems, ...state.homeExpenses].find((item) => item.id === id);
  const confirmed = await confirmAction({
    eyebrow: "CONTROLE FINANCEIRO",
    title: "Reabrir pagamento",
    detail: expense ? `${expense.description} · ${formatMoney(expense.amount_cents)}` : "Despesa selecionada",
    message: "O pagamento será removido e esta despesa voltará a aparecer como pendente.",
    confirmLabel: "Marcar como pendente",
  });
  if (!confirmed) return;
  try {
    await request(`/businesses/${state.me.business_id}/expenses/${id}/pending`, { method: "PATCH" });
    showToast("Despesa marcada como pendente.");
    await Promise.all([loadFinancial(), loadHome()]);
  } catch (error) { showToast(error.message); }
}

async function generateFixedExpenses() {
  const [year, month] = $("report-to").value.split("-").map(Number);
  const target = new Date(Date.UTC(year, month, 1));
  const targetMonth = target.toISOString().slice(0, 10);
  const lastDay = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  const targetEnd = `${targetMonth.slice(0, 8)}${String(lastDay).padStart(2, "0")}`;
  const targetLabel = target.toLocaleDateString("pt-BR", { month: "long", year: "numeric", timeZone: "UTC" });
  const confirmed = await confirmAction({ eyebrow: "CONTROLE FINANCEIRO", title: "Gerar despesas fixas", detail: targetLabel, message: "As despesas fixas cadastradas serão lançadas nesse mês sem duplicar registros existentes.", confirmLabel: "Gerar despesas" });
  if (!confirmed) return;
  const button = $("generate-fixed-expenses"); button.disabled = true; button.textContent = "Gerando...";
  try {
    const created = await request(`/businesses/${state.me.business_id}/expenses/fixed/generate?target_month=${targetMonth}`, { method: "POST" });
    $("report-from").value = targetMonth;
    $("report-to").value = targetEnd;
    $("expense-summary-from").value = targetMonth;
    $("expense-summary-to").value = targetEnd;
    await loadFinancial();
    await loadExpensePeriod();
    showToast(created.length ? `${created.length} despesa${created.length === 1 ? " fixa gerada" : "s fixas geradas"} para ${targetLabel}.` : `As despesas fixas de ${targetLabel} já estavam geradas. Período atualizado.`);
    document.querySelector(".expense-card").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) { showToast(error.message); }
  finally { button.disabled = false; button.textContent = "Gerar próximo mês"; }
}

function openExpenseModal() { state.editingExpenseId = null; $("expense-form").reset(); $("expense-title").textContent = "Nova despesa"; $("save-expense-label").textContent = "Cadastrar despesa"; $("expense-date").value = localDate(); $("expense-error").textContent = ""; $("expense-modal").hidden = false; document.body.classList.add("modal-open"); setTimeout(() => $("expense-description").focus(), 0); }
function openExpenseEditModal(id) {
  const item = state.expensePeriodItems.find((expense) => expense.id === id); if (!item) return;
  state.editingExpenseId = id; $("expense-title").textContent = "Editar despesa"; $("save-expense-label").textContent = "Salvar alterações"; $("expense-error").textContent = "";
  $("expense-category").value = item.category; $("expense-date").value = item.occurred_on; $("expense-description").value = item.description; $("expense-amount").value = (item.amount_cents / 100).toFixed(2); $("expense-fixed").checked = item.is_fixed;
  $("expense-modal").hidden = false; document.body.classList.add("modal-open"); setTimeout(() => $("expense-description").focus(), 0);
}
function closeExpenseModal() { $("expense-modal").hidden = true; document.body.classList.remove("modal-open"); }
async function createExpense(event) {
  event.preventDefault(); const isEditing = Boolean(state.editingExpenseId); $("expense-error").textContent = ""; $("save-expense").disabled = true; $("save-expense-label").textContent = isEditing ? "Salvando..." : "Cadastrando...";
  try {
    const path = isEditing ? `/businesses/${state.me.business_id}/expenses/${state.editingExpenseId}` : `/businesses/${state.me.business_id}/expenses`;
    await request(path, { method: isEditing ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ category: $("expense-category").value, description: $("expense-description").value.trim(), amount_cents: Math.round(Number($("expense-amount").value) * 100), occurred_on: $("expense-date").value, is_fixed: $("expense-fixed").checked }) });
    closeExpenseModal(); showToast(isEditing ? "Alterações salvas com sucesso." : "Despesa cadastrada com sucesso."); await loadFinancial();
  } catch (error) { $("expense-error").textContent = error.message; }
  finally { $("save-expense").disabled = false; $("save-expense-label").textContent = isEditing ? "Salvar alterações" : "Cadastrar despesa"; }
}
async function deleteExpense(id) {
  const expense = state.expensePeriodItems.find((item) => item.id === id);
  const confirmed = await confirmAction({ eyebrow: "CONTROLE FINANCEIRO", title: "Excluir despesa", detail: expense ? `${expense.description} · ${formatMoney(expense.amount_cents)}` : "Despesa selecionada", message: "Esta ação removerá definitivamente o lançamento do relatório financeiro.", confirmLabel: "Excluir despesa", variant: "danger" });
  if (!confirmed) return;
  try { await request(`/businesses/${state.me.business_id}/expenses/${id}`, { method: "DELETE" }); showToast("Despesa excluída."); await loadFinancial(); }
  catch (error) { showToast(error.message); }
}

async function exportFinancialReport() {
  const report = state.financialReport;
  if (!report) { showToast("Atualize o relatório antes de exportar."); return; }
  const button = $("export-report"); button.disabled = true; button.textContent = "Gerando Excel...";
  try {
    const response = await fetch(`${API}/businesses/${state.me.business_id}/reports/financial.xlsx?date_from=${report.date_from}&date_to=${report.date_to}`, { headers: authHeaders() });
    if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.detail || "Não foi possível gerar o Excel."); }
    const url = URL.createObjectURL(await response.blob()); const link = document.createElement("a"); link.href = url; link.download = `osiris-financeiro-${report.date_from}-${report.date_to}.xlsx`; document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url); showToast("Relatório Excel exportado com sucesso.");
  } catch (error) { showToast(error.message); }
  finally { button.disabled = false; button.textContent = "Exportar Excel"; }
}

function customerSegment(customerId) {
  const metrics = state.customerPortfolio.find((item) => item.id === customerId);
  if (!metrics?.last_visit_at) return "inactive";
  const days = Math.floor((new Date(`${localDate()}T12:00:00`).getTime() - new Date(metrics.last_visit_at).getTime()) / 86400000);
  if (days <= 45) return "active";
  if (days <= 90) return "attention";
  return "inactive";
}

function renderCustomerSegments() {
  const counts = { all: state.customers.length, active: 0, attention: 0, inactive: 0 };
  state.customers.forEach((customer) => { counts[customerSegment(customer.id)] += 1; });
  Object.entries(counts).forEach(([segment, count]) => { $(`segment-${segment}`).textContent = count; });
  document.querySelectorAll("[data-customer-segment]").forEach((button) => button.classList.toggle("active", button.dataset.customerSegment === state.customerSegment));
}

function nextBirthday(customer) {
  if (!customer.birth_date) return null;
  const [, month, day] = customer.birth_date.split("-").map(Number); const [year, todayMonth, todayDay] = localDate().split("-").map(Number);
  const today = Date.UTC(year, todayMonth - 1, todayDay); let next = Date.UTC(year, month - 1, day); if (next < today) next = Date.UTC(year + 1, month - 1, day);
  return { customer, days: Math.round((next - today) / 86400000), date: new Date(next) };
}

function renderBirthdays() {
  const birthdays = state.customers.map(nextBirthday).filter((item) => item && item.days <= 30).sort((a, b) => a.days - b.days).slice(0, 5);
  $("birthday-count").textContent = `${birthdays.length} aniversariante${birthdays.length === 1 ? "" : "s"}`;
  $("birthday-list").innerHTML = birthdays.length ? birthdays.map(({ customer, days, date }) => { const when = days === 0 ? "Hoje" : days === 1 ? "Amanhã" : `Em ${days} dias`; const formatted = new Intl.DateTimeFormat("pt-BR", { month: "short", timeZone: "UTC" }).format(date).replace(".", ""); const urgency = days === 0 ? "today" : days === 1 ? "tomorrow" : "upcoming"; return `<article class="birthday-card ${urgency}"><div class="birthday-card-main"><div class="birthday-date"><strong>${String(date.getUTCDate()).padStart(2, "0")}</strong><span>${formatted}</span></div><div class="birthday-person"><span class="birthday-status">${when}</span><h3>${escapeHtml(customer.full_name)}</h3><p>Prepare uma mensagem especial para o cliente.</p></div></div><button class="card-action" data-birthday-whatsapp="${customer.id}" type="button"><span>Enviar parabéns</span><b>→</b></button></article>`; }).join("") : '<div class="empty birthday-empty">Nenhum aniversário nos próximos 30 dias.</div>';
}

function renderPeople() {
  const query = $("customer-search").value.trim().toLocaleLowerCase("pt-BR"); const queryDigits = query.replace(/\D/g, "");
  const segmentedCustomers = state.customers.filter((item) => state.customerSegment === "all" || customerSegment(item.id) === state.customerSegment);
  const visibleCustomers = segmentedCustomers.filter((item) => item.full_name.toLocaleLowerCase("pt-BR").includes(query) || (queryDigits && item.phone.replace(/\D/g, "").includes(queryDigits)));
  $("customer-search-count").textContent = query || state.customerSegment !== "all" ? `${visibleCustomers.length} de ${state.customers.length} clientes` : `${state.customers.length} cliente${state.customers.length === 1 ? "" : "s"}`;
  const labels = { active: "Ativo", attention: "Precisa de atenção", inactive: "Inativo" };
  $("customers").innerHTML = visibleCustomers.map((p) => { const segment = customerSegment(p.id); const metrics = state.customerPortfolio.find((item) => item.id === p.id); const loyalty = metrics?.loyalty_enabled ? `<div class="customer-loyalty"><span>Fidelidade</span><strong>${metrics.loyalty_progress}/${metrics.loyalty_target}</strong><div><i style="width:${Math.round(metrics.loyalty_progress / metrics.loyalty_target * 100)}%"></i></div></div>` : ""; const invite = segment === "active" ? "" : `<button class="card-action wide whatsapp-action" data-customer-whatsapp="${p.id}" type="button">Convidar para voltar</button>`; return `<article class="person-card customer-${segment}"><div class="avatar">${escapeHtml(initials(p.full_name))}</div><h3>${escapeHtml(p.full_name)}</h3><p>${escapeHtml(p.phone)}</p><small>${labels[segment]}</small>${loyalty}<div class="card-actions"><button class="card-action" data-history-id="${p.id}" type="button">Ver histórico</button><button class="card-action" data-edit-customer-id="${p.id}" type="button">Editar cliente</button>${invite}</div></article>`; }).join("") || `<div class="empty">${query ? "Nenhum cliente encontrado para esta busca." : "Nenhum cliente neste segmento."}</div>`;
  renderCustomerSegments();
  $("team").innerHTML = state.barbers.map((p) => `<article class="person-card ${p.is_active ? "" : "inactive"}"><div class="avatar">${escapeHtml(initials(p.full_name))}</div><h3>${escapeHtml(p.full_name)}</h3><p>${escapeHtml(p.phone)}</p><small>${p.is_active ? "● Ativo" : "Inativo"} · Comissão ${p.commission_percentage || 0}%</small><div class="card-actions"><button class="card-action" data-edit-barber-id="${p.id}" type="button">Editar profissional</button><button class="card-action" data-toggle-barber-id="${p.id}" data-active="${p.is_active}" type="button">${p.is_active ? "Desativar" : "Ativar"}</button><button class="card-action" data-time-off-id="${p.id}" type="button">Bloquear agenda</button><button class="card-action" data-barber-access-id="${p.id}" type="button">Criar acesso</button><button class="card-action wide" data-schedule-id="${p.id}" type="button">Horários e comissão</button></div></article>`).join("") || '<div class="empty">Nenhum profissional cadastrado.</div>';
  $("services").innerHTML = state.services.map((s) => `<article class="person-card service-card ${s.is_active ? "" : "inactive"}"><div class="service-top"><div class="avatar">◇</div><strong>${formatMoney(s.price_cents)}</strong></div><h3>${escapeHtml(s.name)}</h3><p>${escapeHtml(s.description || "Sem descrição")}</p><small>${s.duration_minutes} minutos · ${s.is_active ? "Ativo" : "Inativo"}</small><div class="card-actions"><button class="card-action" data-service-edit="${s.id}" type="button">Editar serviço</button><button class="card-action" data-service-toggle="${s.id}" data-active="${s.is_active}" type="button">${s.is_active ? "Desativar" : "Ativar"}</button></div></article>`).join("") || '<div class="empty">Nenhum serviço cadastrado.</div>';
  renderBirthdays();
}

function renderCustomerRanking() {
  const ranking = [...state.customerPortfolio].filter((item) => item.total_spent_cents > 0).sort((a, b) => b.total_spent_cents - a.total_spent_cents || b.completed - a.completed).slice(0, 3);
  $("ranking-note").textContent = ranking.length ? `Top ${ranking.length} por valor gasto` : "Atendimentos concluídos";
  $("customer-ranking-list").innerHTML = ranking.length ? ranking.map((item, index) => `<article class="ranking-card"><span class="ranking-position">${index + 1}º</span><div class="avatar">${escapeHtml(initials(item.full_name))}</div><div><h3>${escapeHtml(item.full_name)}</h3><p>${item.completed} visita${item.completed === 1 ? "" : "s"} concluída${item.completed === 1 ? "" : "s"}</p></div><strong>${formatMoney(item.total_spent_cents)}</strong><button class="card-action" data-ranking-history-id="${item.id}" type="button">Ver histórico</button></article>`).join("") : '<div class="empty ranking-empty">O ranking aparecerá após o primeiro atendimento concluído.</div>';
}

async function loadCustomerPortfolio() {
  try {
    state.customerPortfolio = await request(`/businesses/${state.me.business_id}/customers/portfolio`);
    renderCustomerRanking(); renderPeople();
  } catch (error) { showToast(error.message); }
}

async function openCustomerHistory(customerId) {
  const customer = state.customers.find((item) => item.id === customerId); if (!customer) return;
  const birthDate = customer.birth_date ? customer.birth_date.split("-").reverse().join("/") : null; $("history-title").textContent = customer.full_name; $("history-phone").textContent = `${customer.phone}${birthDate ? ` · Nascimento ${birthDate}` : ""}`; $("history-modal").hidden = false; document.body.classList.add("modal-open");
  $("history-notes").innerHTML = customer.notes ? `<section class="customer-notes"><span>OBSERVAÇÕES E PREFERÊNCIAS</span><p>${escapeHtml(customer.notes)}</p></section>` : "";
  const loyalty = state.customerPortfolio.find((item) => item.id === customerId); const loyaltyWidth = loyalty?.loyalty_target ? Math.round(loyalty.loyalty_progress / loyalty.loyalty_target * 100) : 0;
  $("history-loyalty").innerHTML = loyalty?.loyalty_enabled ? `<section class="loyalty-card"><div><span>FIDELIDADE</span><strong>${loyalty.loyalty_progress} de ${loyalty.loyalty_target} pontos</strong><small>Recompensa: ${escapeHtml(loyalty.loyalty_reward)} · saldo ${loyalty.loyalty_rewards_available}</small></div><div class="loyalty-track"><i style="width:${loyaltyWidth}%"></i></div>${loyalty.loyalty_rewards_available > 0 ? `<button class="primary loyalty-redeem" data-redeem-loyalty="${customerId}" type="button"><span>Resgatar recompensa</span><span>→</span></button>` : ""}</section>` : "";
  $("history-stats").innerHTML = '<div class="empty">Carregando histórico...</div>'; $("history-list").innerHTML = "";
  try {
    const items = await request(`/businesses/${state.me.business_id}/customers/${customerId}/appointments`); const completed = items.filter((item) => item.status === "completed"); const spent = completed.reduce((total, item) => total + (item.price_cents || 0), 0);
    $("history-stats").innerHTML = `<article><span>ATENDIMENTOS</span><strong>${items.length}</strong></article><article><span>CONCLUÍDOS</span><strong>${completed.length}</strong></article><article><span>VALOR GASTO</span><strong>${formatMoney(spent)}</strong></article><article><span>FALTAS</span><strong>${items.filter((item) => item.status === "no_show").length}</strong></article>`;
    $("history-count").textContent = `${items.length} registro${items.length === 1 ? "" : "s"}`;
    $("history-list").innerHTML = items.length ? items.map((item) => { const service = state.services.find((entry) => entry.id === item.service_id); const barber = state.barbers.find((entry) => entry.id === item.barber_id); const date = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", year: "numeric", timeZone: state.business.timezone }).format(new Date(item.starts_at)); return `<article class="history-row"><div class="history-date"><strong>${date}</strong><span>${formatTime(item.starts_at)}</span></div><div><strong>${escapeHtml(service?.name || "Atendimento")}</strong><span>${escapeHtml(barber?.full_name || "Profissional")}${item.price_cents != null ? ` · ${formatMoney(item.price_cents)}` : ""}</span></div><span class="badge ${item.status}">${statusLabel(item.status)}</span></article>`; }).join("") : '<div class="empty">Este cliente ainda não possui atendimentos.</div>';
  } catch (error) { $("history-stats").innerHTML = `<div class="form-error">${error.message}</div>`; }
}
function closeCustomerHistory() { $("history-modal").hidden = true; document.body.classList.remove("modal-open"); }

async function redeemLoyaltyReward(customerId) {
  const metrics = state.customerPortfolio.find((item) => item.id === customerId); if (!metrics?.loyalty_rewards_available) return;
  const confirmed = await confirmAction({ eyebrow: "FIDELIDADE", title: "Resgatar recompensa", detail: metrics.loyalty_reward, message: "O benefício será registrado no histórico deste cliente.", confirmLabel: "Confirmar resgate" });
  if (!confirmed) return;
  const button = $("history-loyalty").querySelector("[data-redeem-loyalty]"); if (button) { button.disabled = true; button.querySelector("span").textContent = "Resgatando..."; }
  try {
    await request(`/businesses/${state.me.business_id}/customers/${customerId}/loyalty/redeem`, { method: "POST" });
    await loadCustomerPortfolio(); await openCustomerHistory(customerId); showToast("Recompensa resgatada com sucesso.");
  } catch (error) { showToast(error.message); if (button) button.disabled = false; }
}

async function exportCustomers() {
  const button = $("export-customers"); button.disabled = true; button.textContent = "Exportando...";
  try {
    const response = await fetch(`${API}/businesses/${state.me.business_id}/customers.xlsx`, { headers: authHeaders() });
    if (response.status === 401) { logout(); throw new Error("Sua sessão expirou. Entre novamente."); }
    if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.detail || "Não foi possível exportar os clientes."); }
    const url = URL.createObjectURL(await response.blob()); const link = document.createElement("a"); link.href = url; link.download = "osiris-clientes.xlsx"; document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url); showToast("Carteira de clientes exportada com sucesso.");
  } catch (error) { showToast(error.message); }
  finally { button.disabled = false; button.textContent = "Exportar Excel"; }
}

function openAppointmentModal() {
  $("appointment-error").textContent = "";
  $("appointment-customer").innerHTML = state.customers.map((c) => `<option value="${c.id}">${escapeHtml(c.full_name)}</option>`).join("");
  $("appointment-barber").innerHTML = state.barbers.filter((b) => b.is_active).map((b) => `<option value="${b.id}" ${b.id === $("barber-filter").value ? "selected" : ""}>${escapeHtml(b.full_name)}</option>`).join("");
  $("appointment-service").innerHTML = state.services.filter((s) => s.is_active).map((s) => `<option value="${s.id}">${escapeHtml(s.name)} · ${s.duration_minutes} min · ${formatMoney(s.price_cents)}</option>`).join("");
  $("appointment-date").value = $("date-filter").value;
  $("appointment-modal").hidden = false; document.body.classList.add("modal-open"); loadBookingSlots();
}

function closeAppointmentModal() { $("appointment-modal").hidden = true; document.body.classList.remove("modal-open"); }

function openRescheduleModal(id) {
  const appointment = state.appointments.find((item) => item.id === id); if (!appointment) return;
  const customer = state.customers.find((item) => item.id === appointment.customer_id); state.rescheduleAppointmentId = id;
  $("reschedule-customer").textContent = customer?.full_name || "Cliente"; $("reschedule-error").textContent = "";
  $("reschedule-barber").innerHTML = state.barbers.filter((item) => item.is_active).map((item) => `<option value="${item.id}" ${item.id === appointment.barber_id ? "selected" : ""}>${escapeHtml(item.full_name)}</option>`).join("");
  $("reschedule-service").innerHTML = state.services.filter((item) => item.is_active).map((item) => `<option value="${item.id}" ${item.id === appointment.service_id ? "selected" : ""}>${escapeHtml(item.name)} · ${item.duration_minutes} min</option>`).join("");
  $("reschedule-date").value = new Intl.DateTimeFormat("en-CA", { timeZone: state.business.timezone }).format(new Date(appointment.starts_at)); $("reschedule-date").min = localDate();
  $("reschedule-modal").hidden = false; document.body.classList.add("modal-open"); loadRescheduleSlots();
}
function closeRescheduleModal() { $("reschedule-modal").hidden = true; document.body.classList.remove("modal-open"); }
async function loadRescheduleSlots() {
  const select = $("reschedule-slot"), barberId = $("reschedule-barber").value, date = $("reschedule-date").value, service = state.services.find((item) => item.id === $("reschedule-service").value);
  select.disabled = true; select.innerHTML = '<option value="">Carregando horários...</option>';
  if (!barberId || !date || !service) { select.innerHTML = '<option value="">Selecione as opções</option>'; select.disabled = false; return; }
  try {
    const data = await request(`/businesses/${state.me.business_id}/barbers/${barberId}/availability?appointment_date=${date}`); const duration = service.duration_minutes * 60000;
    const slots = data.slots.filter((slot) => { const start = new Date(slot.starts_at).getTime(), target = start + duration; let cursor = start; for (const candidate of data.slots) { if (new Date(candidate.starts_at).getTime() === cursor) cursor = new Date(candidate.ends_at).getTime(); if (cursor >= target) return true; } return false; });
    select.innerHTML = slots.length ? `<option value="">Selecione</option>${slots.map((slot) => `<option value="${slot.starts_at}">${formatTime(slot.starts_at)}</option>`).join("")}` : '<option value="">Nenhum horário livre</option>';
  } catch (error) { select.innerHTML = '<option value="">Não foi possível carregar</option>'; $("reschedule-error").textContent = error.message; }
  finally { select.disabled = false; }
}
async function rescheduleAppointment(event) {
  event.preventDefault(); $("reschedule-error").textContent = ""; $("save-reschedule").disabled = true; $("save-reschedule-label").textContent = "Salvando...";
  try {
    await request(`/businesses/${state.me.business_id}/appointments/${state.rescheduleAppointmentId}/reschedule`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ barber_id: $("reschedule-barber").value, service_id: $("reschedule-service").value, starts_at: $("reschedule-slot").value }) });
    $("date-filter").value = $("reschedule-date").value; $("barber-filter").value = $("reschedule-barber").value; closeRescheduleModal(); showToast("Alterações salvas com sucesso."); await Promise.all([loadAgenda(), loadHome()]);
  } catch (error) { $("reschedule-error").textContent = error.message; }
  finally { $("save-reschedule").disabled = false; $("save-reschedule-label").textContent = "Salvar novo horário"; }
}

function openPersonModal(kind) {
  state.personKind = kind; state.editingCustomerId = null; state.editingBarberId = null; const isCustomer = kind === "customer";
  $("person-eyebrow").textContent = isCustomer ? "NOVO CLIENTE" : "NOVO PROFISSIONAL";
  $("person-title").textContent = isCustomer ? "Cadastrar cliente" : "Cadastrar profissional";
  $("save-person-label").textContent = isCustomer ? "Cadastrar cliente" : "Cadastrar profissional";
  $("person-notes-field").hidden = !isCustomer;
  $("person-birth-date-field").hidden = !isCustomer;
  $("person-error").textContent = ""; $("person-form").reset(); $("person-modal").hidden = false; document.body.classList.add("modal-open"); setTimeout(() => $("person-name").focus(), 0);
}

function openCustomerEditModal(customerId) {
  const customer = state.customers.find((item) => item.id === customerId); if (!customer) return;
  state.personKind = "customer"; state.editingCustomerId = customerId;
  $("person-eyebrow").textContent = "DADOS DO CLIENTE"; $("person-title").textContent = "Editar cliente"; $("save-person-label").textContent = "Salvar alterações";
  $("person-notes-field").hidden = false; $("person-birth-date-field").hidden = false; $("person-error").textContent = ""; $("person-name").value = customer.full_name; $("person-phone").value = customer.phone; $("person-notes").value = customer.notes || ""; $("person-birth-date").value = customer.birth_date || "";
  $("person-modal").hidden = false; document.body.classList.add("modal-open"); setTimeout(() => $("person-name").focus(), 0);
}

function openBarberEditModal(barberId) {
  const barber = state.barbers.find((item) => item.id === barberId); if (!barber) return;
  state.personKind = "barber"; state.editingCustomerId = null; state.editingBarberId = barberId;
  $("person-eyebrow").textContent = "DADOS DO PROFISSIONAL"; $("person-title").textContent = "Editar profissional"; $("save-person-label").textContent = "Salvar alterações";
  $("person-notes-field").hidden = true; $("person-birth-date-field").hidden = true; $("person-error").textContent = ""; $("person-name").value = barber.full_name; $("person-phone").value = barber.phone; $("person-notes").value = ""; $("person-birth-date").value = "";
  $("person-modal").hidden = false; document.body.classList.add("modal-open"); setTimeout(() => $("person-name").focus(), 0);
}

function closePersonModal() { $("person-modal").hidden = true; document.body.classList.remove("modal-open"); }

async function createPerson(event) {
  event.preventDefault(); const isCustomer = state.personKind === "customer"; const resource = isCustomer ? "customers" : "barbers";
  const isEditingCustomer = isCustomer && state.editingCustomerId; const isEditingBarber = !isCustomer && state.editingBarberId; const isEditing = isEditingCustomer || isEditingBarber; $("person-error").textContent = ""; $("save-person").disabled = true; $("save-person-label").textContent = isEditing ? "Salvando..." : "Cadastrando...";
  try {
    const editId = isEditingCustomer ? state.editingCustomerId : state.editingBarberId; const path = isEditing ? `/businesses/${state.me.business_id}/${resource}/${editId}` : `/businesses/${state.me.business_id}/${resource}`;
    const payload = { full_name: $("person-name").value.trim(), phone: $("person-phone").value.trim() }; if (isCustomer) { payload.notes = $("person-notes").value.trim() || null; payload.birth_date = $("person-birth-date").value || null; }
    const saved = await request(path, { method: isEditing ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (isEditingCustomer) state.customers = state.customers.map((item) => item.id === saved.id ? saved : item); else if (isEditingBarber) state.barbers = state.barbers.map((item) => item.id === saved.id ? saved : item); else if (isCustomer) state.customers.push(saved); else state.barbers.push(saved);
    renderPeople(); refreshSelectors(); closePersonModal(); showToast(isEditingCustomer || isEditingBarber ? "Alterações salvas com sucesso." : isCustomer ? "Cliente cadastrado com sucesso." : "Profissional cadastrado com sucesso."); if (!isCustomer && !isEditingBarber) setTimeout(() => openScheduleModal(saved.id), 250);
  } catch (error) { $("person-error").textContent = error.message; }
  finally { $("save-person").disabled = false; $("save-person-label").textContent = isEditing ? "Salvar alterações" : isCustomer ? "Cadastrar cliente" : "Cadastrar profissional"; }
}

function refreshSelectors() {
  const selectedBarber = $("barber-filter").value;
  $("barber-filter").innerHTML = `<option value="all">Todos os profissionais</option>${state.barbers.map((b) => `<option value="${b.id}">${b.full_name}</option>`).join("")}`;
  if (selectedBarber === "all" || state.barbers.some((b) => b.id === selectedBarber)) $("barber-filter").value = selectedBarber;
}

async function toggleBarber(id, isActive) {
  try {
    const updated = await request(`/businesses/${state.me.business_id}/barbers/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_active: !isActive }) });
    state.barbers = state.barbers.map((item) => item.id === updated.id ? updated : item); renderPeople(); refreshSelectors(); showToast(updated.is_active ? "Profissional ativado." : "Profissional desativado para novos agendamentos.");
    if ($("barber-filter").value) await loadAgenda();
  } catch (error) { showToast(error.message); }
}

const weekdayNames = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];
function renderCustomScheduleRows(schedules = []) {
  $("schedule-custom-fields").innerHTML = weekdayNames.map((name, weekday) => { const schedule = schedules.find((item) => item.weekday === weekday); return `<div class="schedule-day-row" data-schedule-row="${weekday}"><strong>${name}</strong><label>Início<input data-day-start="${weekday}" type="time" value="${schedule?.starts_at.slice(0, 5) || $("schedule-start").value}" /></label><label>Fim<input data-day-end="${weekday}" type="time" value="${schedule?.ends_at.slice(0, 5) || $("schedule-end").value}" /></label><label>Duração<select data-day-duration="${weekday}"><option value="30" ${schedule?.slot_duration_minutes === 30 ? "selected" : ""}>30 min</option><option value="45" ${schedule?.slot_duration_minutes === 45 ? "selected" : ""}>45 min</option><option value="60" ${schedule?.slot_duration_minutes === 60 ? "selected" : ""}>60 min</option></select></label><label>Pausa início<input data-day-break-start="${weekday}" type="time" value="${schedule?.break_starts_at?.slice(0, 5) || ""}" /></label><label>Pausa fim<input data-day-break-end="${weekday}" type="time" value="${schedule?.break_ends_at?.slice(0, 5) || ""}" /></label></div>`; }).join(""); updateCustomScheduleRows();
}
function updateCustomScheduleRows() { document.querySelectorAll("[data-schedule-row]").forEach((row) => { const active = document.querySelector(`input[name="weekday"][value="${row.dataset.scheduleRow}"]`)?.checked; row.classList.toggle("inactive", !active); row.querySelectorAll("input,select").forEach((input) => input.disabled = !active); }); }
function toggleCustomSchedule() { const custom = $("custom-schedule").checked; $("schedule-default-fields").hidden = custom; $("schedule-custom-fields").hidden = !custom; $("schedule-hint").textContent = custom ? "Defina o expediente individualmente para cada dia selecionado." : "A jornada será aplicada a todos os dias selecionados."; if (custom) renderCustomScheduleRows(state.currentSchedules || []); }

async function openScheduleModal(barberId) {
  const barber = state.barbers.find((item) => item.id === barberId); state.scheduleBarberId = barberId;
  $("schedule-professional").textContent = barber ? barber.full_name : "Profissional"; $("schedule-error").textContent = "";
  document.querySelectorAll('input[name="weekday"]').forEach((input) => input.checked = false); $("schedule-start").value = "09:00"; $("schedule-end").value = "18:00"; $("schedule-duration").value = "30"; $("schedule-break-start").value = ""; $("schedule-break-end").value = ""; $("custom-schedule").checked = false; $("schedule-default-fields").hidden = false; $("schedule-custom-fields").hidden = true; $("barber-commission").value = String(barber?.commission_percentage || 0);
  $("schedule-modal").hidden = false; document.body.classList.add("modal-open"); $("save-schedule").disabled = true; $("save-schedule-label").textContent = "Carregando...";
  try {
    const schedules = await request(`/businesses/${state.me.business_id}/barbers/${barberId}/schedule`);
    state.currentSchedules = schedules;
    state.scheduleExistingWeekdays = schedules.map((schedule) => String(schedule.weekday));
    schedules.forEach((schedule) => { const input = document.querySelector(`input[name="weekday"][value="${schedule.weekday}"]`); if (input) input.checked = true; });
    if (schedules.length) { $("schedule-start").value = schedules[0].starts_at.slice(0, 5); $("schedule-end").value = schedules[0].ends_at.slice(0, 5); $("schedule-duration").value = String(schedules[0].slot_duration_minutes); $("schedule-break-start").value = schedules[0].break_starts_at?.slice(0, 5) || ""; $("schedule-break-end").value = schedules[0].break_ends_at?.slice(0, 5) || ""; const hasDifferentHours = schedules.some((item) => item.starts_at !== schedules[0].starts_at || item.ends_at !== schedules[0].ends_at || item.slot_duration_minutes !== schedules[0].slot_duration_minutes || item.break_starts_at !== schedules[0].break_starts_at || item.break_ends_at !== schedules[0].break_ends_at); if (hasDifferentHours) { $("custom-schedule").checked = true; toggleCustomSchedule(); } }
  } catch (error) { $("schedule-error").textContent = error.message; }
  finally { $("save-schedule").disabled = false; $("save-schedule-label").textContent = "Salvar alterações"; }
}

function closeScheduleModal() { $("schedule-modal").hidden = true; document.body.classList.remove("modal-open"); }

async function openTimeOffModal(barberId) {
  state.timeOffBarberId = barberId; const barber = state.barbers.find((item) => item.id === barberId);
  $("time-off-professional").textContent = barber?.full_name || "Profissional"; $("time-off-form").reset(); $("time-off-error").textContent = ""; $("time-off-modal").hidden = false; document.body.classList.add("modal-open"); await loadTimeOff();
}
function closeTimeOffModal() { $("time-off-modal").hidden = true; document.body.classList.remove("modal-open"); }
async function loadTimeOff() {
  $("time-off-list").innerHTML = '<div class="empty">Carregando...</div>';
  try { const items = await request(`/businesses/${state.me.business_id}/barbers/${state.timeOffBarberId}/time-off`); $("time-off-list").innerHTML = items.length ? items.map((item) => `<article class="time-off-row"><div><strong>${escapeHtml(item.reason)}</strong><span>${new Date(item.starts_at).toLocaleString("pt-BR")} até ${new Date(item.ends_at).toLocaleString("pt-BR")}</span></div><button data-delete-time-off="${item.id}" type="button">Excluir</button></article>`).join("") : '<div class="empty">Nenhum bloqueio cadastrado.</div>'; } catch (error) { $("time-off-error").textContent = error.message; }
}
async function createTimeOff(event) {
  event.preventDefault(); const start = new Date($("time-off-start").value), end = new Date($("time-off-end").value); if (end <= start) { $("time-off-error").textContent = "O fim deve ser posterior ao início."; return; }
  $("save-time-off").disabled = true; $("save-time-off-label").textContent = "Salvando..."; $("time-off-error").textContent = "";
  try { await request(`/businesses/${state.me.business_id}/barbers/${state.timeOffBarberId}/time-off`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reason: $("time-off-reason").value.trim(), starts_at: start.toISOString(), ends_at: end.toISOString() }) }); $("time-off-form").reset(); closeTimeOffModal(); showToast("Alterações salvas com sucesso."); } catch (error) { $("time-off-error").textContent = error.message; } finally { $("save-time-off").disabled = false; $("save-time-off-label").textContent = "Criar bloqueio"; }
}
async function deleteTimeOff(id) { const confirmed = await confirmAction({ eyebrow: "DISPONIBILIDADE", title: "Excluir bloqueio", detail: "Período indisponível selecionado", message: "O profissional voltará a aparecer como disponível nesse período.", confirmLabel: "Excluir bloqueio", variant: "danger" }); if (!confirmed) return; try { await request(`/businesses/${state.me.business_id}/barbers/${state.timeOffBarberId}/time-off/${id}`, { method: "DELETE" }); await loadTimeOff(); showToast("Bloqueio removido."); } catch (error) { $("time-off-error").textContent = error.message; } }

async function saveSchedule(event) {
  event.preventDefault(); const weekdays = [...document.querySelectorAll('input[name="weekday"]:checked')].map((input) => input.value);
  if (!weekdays.length) { $("schedule-error").textContent = "Selecione pelo menos um dia de atendimento."; return; }
  const starts_at = $("schedule-start").value; const ends_at = $("schedule-end").value;
  if (!$("custom-schedule").checked && ends_at <= starts_at) { $("schedule-error").textContent = "O horário final deve ser posterior ao inicial."; return; }
  $("schedule-error").textContent = ""; $("save-schedule").disabled = true; $("save-schedule-label").textContent = "Salvando...";
  try {
    const removedWeekdays = state.scheduleExistingWeekdays.filter((weekday) => !weekdays.includes(weekday));
    const updates = weekdays.map((weekday) => { const payload = $("custom-schedule").checked ? { starts_at: document.querySelector(`[data-day-start="${weekday}"]`).value, ends_at: document.querySelector(`[data-day-end="${weekday}"]`).value, slot_duration_minutes: Number(document.querySelector(`[data-day-duration="${weekday}"]`).value), break_starts_at: document.querySelector(`[data-day-break-start="${weekday}"]`).value || null, break_ends_at: document.querySelector(`[data-day-break-end="${weekday}"]`).value || null } : { starts_at, ends_at, slot_duration_minutes: Number($("schedule-duration").value), break_starts_at: $("schedule-break-start").value || null, break_ends_at: $("schedule-break-end").value || null }; if (payload.ends_at <= payload.starts_at) throw new Error(`${weekdayNames[Number(weekday)]}: o fim deve ser posterior ao início.`); if ((payload.break_starts_at || payload.break_ends_at) && !(payload.break_starts_at && payload.break_ends_at && payload.starts_at <= payload.break_starts_at && payload.break_starts_at < payload.break_ends_at && payload.break_ends_at <= payload.ends_at)) throw new Error(`${weekdayNames[Number(weekday)]}: confira o intervalo da pausa.`); return request(`/businesses/${state.me.business_id}/barbers/${state.scheduleBarberId}/schedule/${weekday}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); });
    updates.push(...removedWeekdays.map((weekday) => request(`/businesses/${state.me.business_id}/barbers/${state.scheduleBarberId}/schedule/${weekday}`, { method: "DELETE" })));
    updates.push(request(`/businesses/${state.me.business_id}/barbers/${state.scheduleBarberId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ commission_percentage: Number($("barber-commission").value) }) }));
    const results = await Promise.all(updates); const updatedBarber = results.find((item) => item?.full_name); const index = state.barbers.findIndex((item) => item.id === updatedBarber.id); state.barbers[index] = updatedBarber; renderPeople();
    closeScheduleModal(); showToast("Alterações salvas com sucesso."); if ($("barber-filter").value === state.scheduleBarberId) await loadAgenda();
  } catch (error) { $("schedule-error").textContent = error.message; }
  finally { $("save-schedule").disabled = false; $("save-schedule-label").textContent = "Salvar alterações"; }
}

async function loadBookingSlots() {
  const select = $("appointment-slot"); const barberId = $("appointment-barber").value; const date = $("appointment-date").value;
  select.disabled = true; select.innerHTML = '<option value="">Carregando horários...</option>';
  if (!barberId || !date) { select.innerHTML = '<option value="">Selecione data e profissional</option>'; return; }
  try {
    const data = await request(`/businesses/${state.me.business_id}/barbers/${barberId}/availability?appointment_date=${date}`);
    state.bookingSlots = data.slots; renderBookingSlots();
  } catch (error) { select.innerHTML = '<option value="">Não foi possível carregar</option>'; $("appointment-error").textContent = error.message; }
  finally { select.disabled = false; }
}

function renderBookingSlots() {
  const select = $("appointment-slot"); const service = state.services.find((s) => s.id === $("appointment-service").value);
  if (!service) { select.innerHTML = '<option value="">Cadastre ou selecione um serviço</option>'; return; }
  const durationMs = service.duration_minutes * 60000;
  const valid = state.bookingSlots.filter((slot) => {
    const start = new Date(slot.starts_at).getTime(); const target = start + durationMs; let cursor = start;
    for (const candidate of state.bookingSlots) { if (new Date(candidate.starts_at).getTime() === cursor) cursor = new Date(candidate.ends_at).getTime(); if (cursor >= target) return true; }
    return false;
  }).map((slot) => ({ starts_at: slot.starts_at, ends_at: new Date(new Date(slot.starts_at).getTime() + durationMs).toISOString() }));
  select.innerHTML = valid.length ? `<option value="">Selecione um horário</option>${valid.map((slot) => `<option value="${slot.starts_at}|${slot.ends_at}">${formatTime(slot.starts_at)} – ${formatTime(slot.ends_at)}</option>`).join("")}` : '<option value="">Sem horário suficiente para este serviço</option>';
}

async function createAppointment(event) {
  event.preventDefault(); $("appointment-error").textContent = "";
  const [starts_at, ends_at] = $("appointment-slot").value.split("|");
  if (!starts_at || !ends_at) { $("appointment-error").textContent = "Escolha um horário disponível."; return; }
  $("save-appointment").disabled = true; $("save-appointment-label").textContent = "Criando...";
  try {
    await request(`/businesses/${state.me.business_id}/appointments`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ barber_id: $("appointment-barber").value, customer_id: $("appointment-customer").value, service_id: $("appointment-service").value, starts_at, ends_at, notes: $("appointment-notes").value.trim() || null }) });
    $("date-filter").value = $("appointment-date").value; $("barber-filter").value = $("appointment-barber").value; closeAppointmentModal(); $("appointment-form").reset(); showToast("Agendamento criado com sucesso."); await Promise.all([loadAgenda(), loadHome()]);
  } catch (error) { $("appointment-error").textContent = error.message; }
  finally { $("save-appointment").disabled = false; $("save-appointment-label").textContent = "Criar agendamento"; }
}

function openServiceModal() { state.editingServiceId = null; $("service-form").reset(); $("service-title").textContent = "Novo serviço"; $("save-service-label").textContent = "Cadastrar serviço"; $("service-error").textContent = ""; $("service-modal").hidden = false; document.body.classList.add("modal-open"); setTimeout(() => $("service-name").focus(), 0); }
function openServiceEditModal(id) {
  const service = state.services.find((item) => item.id === id); if (!service) return;
  state.editingServiceId = id; $("service-title").textContent = "Editar serviço"; $("save-service-label").textContent = "Salvar alterações"; $("service-error").textContent = "";
  $("service-name").value = service.name; $("service-duration").value = String(service.duration_minutes); $("service-price").value = (service.price_cents / 100).toFixed(2); $("service-description").value = service.description || "";
  $("service-modal").hidden = false; document.body.classList.add("modal-open"); setTimeout(() => $("service-name").focus(), 0);
}
function closeServiceModal() { $("service-modal").hidden = true; document.body.classList.remove("modal-open"); }
async function createService(event) {
  event.preventDefault(); const isEditing = Boolean(state.editingServiceId); $("service-error").textContent = ""; $("save-service").disabled = true; $("save-service-label").textContent = isEditing ? "Salvando..." : "Cadastrando...";
  try {
    const path = isEditing ? `/businesses/${state.me.business_id}/services/${state.editingServiceId}` : `/businesses/${state.me.business_id}/services`;
    const saved = await request(path, { method: isEditing ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: $("service-name").value.trim(), description: $("service-description").value.trim() || null, duration_minutes: Number($("service-duration").value), price_cents: Math.round(Number($("service-price").value) * 100) }) });
    if (isEditing) state.services = state.services.map((item) => item.id === saved.id ? saved : item); else state.services.push(saved);
    state.services.sort((a, b) => a.name.localeCompare(b.name)); renderPeople(); closeServiceModal(); showToast(isEditing ? "Alterações salvas com sucesso." : "Serviço cadastrado com sucesso.");
  } catch (error) { $("service-error").textContent = error.message; }
  finally { $("save-service").disabled = false; $("save-service-label").textContent = isEditing ? "Salvar alterações" : "Cadastrar serviço"; }
}
async function toggleService(id, isActive) {
  try { const updated = await request(`/businesses/${state.me.business_id}/services/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_active: !isActive }) }); const index = state.services.findIndex((s) => s.id === id); state.services[index] = updated; renderPeople(); showToast(updated.is_active ? "Serviço ativado." : "Serviço desativado."); }
  catch (error) { showToast(error.message); }
}

function openPaymentModal(id) { const appointment = state.appointments.find((a) => a.id === id); const service = state.services.find((s) => s.id === appointment?.service_id); state.paymentAppointmentId = id; $("payment-summary").textContent = `${appointment?.service_name || service?.name || "Atendimento"} · ${formatMoney(appointment?.price_cents || 0)}`; $("payment-error").textContent = ""; $("payment-modal").hidden = false; document.body.classList.add("modal-open"); }
function closePaymentModal() { $("payment-modal").hidden = true; document.body.classList.remove("modal-open"); }
async function completeAppointment(event) { event.preventDefault(); $("payment-error").textContent = ""; $("save-payment").disabled = true; $("save-payment-label").textContent = "Concluindo..."; try { const path = state.me.role === "barber" ? `/auth/barber/appointments/${state.paymentAppointmentId}/complete` : `/businesses/${state.me.business_id}/appointments/${state.paymentAppointmentId}/complete`; await request(path, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ payment_method: $("payment-method").value }) }); closePaymentModal(); showToast("Atendimento concluído e pagamento registrado."); if (state.me.role === "barber") await loadAgenda(); else await Promise.all([loadAgenda(), loadHome()]); } catch (error) { $("payment-error").textContent = error.message; } finally { $("save-payment").disabled = false; $("save-payment-label").textContent = "Concluir atendimento"; } }

async function changeStatus(action, id) { try { const path = state.me.role === "barber" ? `/auth/barber/appointments/${id}/${action}` : `/businesses/${state.me.business_id}/appointments/${id}/${action}`; await request(path, { method: "PATCH" }); showToast(action === "confirm" ? "Agendamento confirmado." : action === "no-show" ? "Falta registrada." : "Agendamento cancelado."); if (state.me.role === "barber") await loadAgenda(); else await Promise.all([loadAgenda(), loadHome()]); } catch (error) { showToast(error.message); } }
function normalizeWhatsAppPhone(value) { let phone = value.replace(/\D/g, ""); if (phone.startsWith("0")) phone = phone.slice(1); if (phone.length === 10 || phone.length === 11) phone = `55${phone}`; return phone; }
function inviteCustomerBack(customerId) {
  const customer = state.customers.find((item) => item.id === customerId); if (!customer) return;
  const phone = normalizeWhatsAppPhone(customer.phone); if (phone.length < 12) { showToast("Confira o telefone cadastrado deste cliente."); return; }
  const greetingName = customer.full_name.split(" ")[0]; const bookingLink = `${location.origin}/dashboard/booking/?business_id=${state.me.business_id}`; const message = `Olá, ${greetingName}! Sentimos sua falta na ${state.business.name}. Que tal agendar seu próximo horário? Você pode escolher o melhor dia e horário aqui: ${bookingLink}`;
  window.open(`https://wa.me/${phone}?text=${encodeURIComponent(message)}`, "_blank", "noopener");
}
function sendBirthdayMessage(customerId) {
  const customer = state.customers.find((item) => item.id === customerId); if (!customer) return;
  const phone = normalizeWhatsAppPhone(customer.phone); if (phone.length < 12) { showToast("Confira o telefone cadastrado deste cliente."); return; }
  const greetingName = customer.full_name.split(" ")[0]; const bookingLink = `${location.origin}/dashboard/booking/?business_id=${state.me.business_id}`; const message = `Feliz aniversário, ${greetingName}! Toda a equipe da ${state.business.name} deseja um dia especial para você. Quando quiser cuidar do visual, estamos por aqui: ${bookingLink}`;
  window.open(`https://wa.me/${phone}?text=${encodeURIComponent(message)}`, "_blank", "noopener");
}
function sendWhatsAppReminder(id) {
  const appointment = state.appointments.find((item) => item.id === id); if (!appointment) return;
  const customer = state.customers.find((item) => item.id === appointment.customer_id); const service = state.services.find((item) => item.id === appointment.service_id);
  const customerPhone = appointment.customer_phone || customer?.phone || ""; const customerName = appointment.customer_name || customer?.full_name || "Cliente"; const serviceName = appointment.service_name || service?.name || "um atendimento";
  if (!customerPhone) { showToast("Este cliente não possui WhatsApp cadastrado."); return; }
  const phone = normalizeWhatsAppPhone(customerPhone);
  if (phone.length < 12) { showToast("Confira o telefone cadastrado deste cliente."); return; }
  const greetingName = customerName.split(" ")[0]; const confirmationLink = `${location.origin}/dashboard/booking/?booking_token=${appointment.public_token}`; const message = `Olá, ${greetingName}! Lembramos que você tem ${serviceName} agendado na ${state.business.name}, ${formatAppointmentDate(appointment.starts_at)}, às ${formatTime(appointment.starts_at)}. Confirme sua presença ou cancele pelo link: ${confirmationLink}`;
  window.open(`https://wa.me/${phone}?text=${encodeURIComponent(message)}`, "_blank", "noopener");
}
function logout() { sessionStorage.removeItem("osiris_token"); state.token = null; state.me = null; document.body.classList.remove("barber-session"); document.querySelectorAll(".nav-item").forEach((button) => { button.hidden = false; button.classList.toggle("active", button.dataset.view === "inicio"); }); document.querySelectorAll(".panel-view").forEach((panel) => { panel.hidden = panel.id !== "inicio-panel"; }); $("barber-filter").disabled = false; $("new-appointment").hidden = false; $("save-appointment-notes").hidden = false; $("loading-view").hidden = true; $("app-view").hidden = true; $("login-view").hidden = false; window.scrollTo(0, 0); }

function openBarberAccessModal(barberId) { const barber = state.barbers.find((item) => item.id === barberId); if (!barber) return; state.accessBarberId = barberId; $("barber-access-form").reset(); $("barber-access-professional").textContent = barber.full_name; $("barber-access-error").textContent = ""; $("barber-access-modal").hidden = false; document.body.classList.add("modal-open"); setTimeout(() => $("barber-access-email").focus(), 0); }
function closeBarberAccessModal() { $("barber-access-modal").hidden = true; document.body.classList.remove("modal-open"); state.accessBarberId = null; }
async function createBarberAccess(event) { event.preventDefault(); $("barber-access-error").textContent = ""; $("save-barber-access").disabled = true; $("save-barber-access-label").textContent = "Criando..."; try { await request("/auth/barber-accounts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ barber_id: state.accessBarberId, email: $("barber-access-email").value.trim(), password: $("barber-access-password").value }) }); closeBarberAccessModal(); showToast("Acesso do profissional criado com sucesso."); } catch (error) { $("barber-access-error").textContent = error.message === "This professional already has a login account." ? "Este profissional já possui um acesso." : error.message === "An account with this email already exists." ? "Este e-mail já está sendo usado." : error.message; } finally { $("save-barber-access").disabled = false; $("save-barber-access-label").textContent = "Criar acesso"; } }

function businessUpdatePayload() {
  return { name: $("business-settings-name").value.trim(), phone: $("business-settings-phone").value.trim(), timezone: $("business-settings-timezone").value, loyalty_enabled: $("loyalty-enabled").checked, loyalty_target: Number($("loyalty-target").value), loyalty_reward: $("loyalty-reward").value.trim(), monthly_revenue_goal_cents: Math.round(Number($("revenue-goal-input").value || 0) * 100) };
}

function renderRevenueGoal(revenue) { const goal = state.business.monthly_revenue_goal_cents || 0, percent = goal ? Math.min(100, Math.round(revenue / goal * 100)) : 0; $("revenue-goal-progress").style.width = `${percent}%`; $("revenue-goal-progress").parentElement.setAttribute("aria-valuenow", percent); $("revenue-goal-title").textContent = goal ? `${percent}% da meta alcançada` : "Defina seu objetivo"; $("revenue-goal-detail").textContent = goal ? revenue >= goal ? `Meta de ${formatMoney(goal)} alcançada!` : `${formatMoney(revenue)} de ${formatMoney(goal)} · faltam ${formatMoney(goal - revenue)}` : "Cadastre uma meta para acompanhar a evolução do faturamento."; }
async function saveRevenueGoal(event) { event.preventDefault(); try { state.business = await request(`/businesses/${state.me.business_id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(businessUpdatePayload()) }); renderRevenueGoal(state.financialReport?.total_revenue_cents || 0); await loadRevenueGoalHistory(); showToast("Meta mensal salva com sucesso."); } catch (error) { showToast(error.message); } }

async function loadRevenueGoalHistory() {
  const year = Number($("goal-history-year").value), target = $("goal-month-cards"), button = $("refresh-goal-history"), goal = state.business?.monthly_revenue_goal_cents || 0;
  if (!Number.isInteger(year) || year < 2020 || year > 2100) { showToast("Escolha um ano válido."); return; }
  if (!goal) { $("goal-year-summary").innerHTML = ""; target.innerHTML = '<div class="empty">Defina uma meta mensal para acompanhar o ano.</div>'; return; }
  button.disabled = true;
  try {
    const report = await request(`/businesses/${state.me.business_id}/reports/financial?date_from=${year}-01-01&date_to=${year}-12-31`);
    const revenues = Array(12).fill(0); report.daily.forEach((item) => { revenues[Number(item.date.slice(5, 7)) - 1] += item.revenue_cents; });
    const months = revenues.map((revenue, index) => ({ index, revenue, difference: revenue - goal, remainingDeficit: Math.max(0, goal - revenue), compensationUsed: 0 }));
    const deficits = [];
    months.forEach((month) => {
      if (month.remainingDeficit) { deficits.push(month); return; }
      let available = Math.max(0, month.difference);
      for (const deficit of deficits) { if (!available) break; const compensation = Math.min(available, deficit.remainingDeficit); deficit.remainingDeficit -= compensation; available -= compensation; month.compensationUsed += compensation; }
    });
    const totalRevenue = revenues.reduce((sum, value) => sum + value, 0), annualTarget = goal * 12, annualDifference = totalRevenue - annualTarget;
    const compensated = months.filter((month) => month.difference < 0 && month.remainingDeficit === 0).length, pendingDeficit = months.reduce((sum, month) => sum + month.remainingDeficit, 0);
    $("goal-year-summary").innerHTML = `<article><span>FATURAMENTO NO ANO</span><strong>${formatMoney(totalRevenue)}</strong></article><article><span>META ANUAL EQUIVALENTE</span><strong>${formatMoney(annualTarget)}</strong></article><article class="${annualDifference >= 0 ? "positive" : "negative"}"><span>SALDO ACUMULADO</span><strong>${annualDifference >= 0 ? "+" : "−"}${formatMoney(Math.abs(annualDifference))}</strong></article><article><span>METAS COMPENSADAS</span><strong>${compensated}</strong><small>${pendingDeficit ? `${formatMoney(pendingDeficit)} ainda faltam` : "nenhum déficit pendente"}</small></article>`;
    target.innerHTML = months.map((month) => {
      const monthName = new Date(Date.UTC(year, month.index, 1)).toLocaleDateString("pt-BR", { month: "long", timeZone: "UTC" });
      let status = "Meta alcançada", detail = "Objetivo atingido exatamente", css = "reached";
      if (month.difference > 0) { status = "Meta superada"; detail = `Excedente de ${formatMoney(month.difference)}${month.compensationUsed ? ` · ${formatMoney(month.compensationUsed)} usados para compensar` : ""}`; css = "exceeded"; }
      if (month.difference < 0 && month.remainingDeficit === 0) { status = "Meta compensada"; detail = `Déficit de ${formatMoney(Math.abs(month.difference))} coberto por meses seguintes`; css = "compensated"; }
      else if (month.difference < 0) { status = "Meta não alcançada"; detail = `Ainda faltam ${formatMoney(month.remainingDeficit)}`; css = "missed"; }
      const progress = Math.min(100, Math.round(month.revenue / goal * 100));
      return `<article class="goal-month-card ${css}" data-goal-month="${year}-${String(month.index + 1).padStart(2, "0")}" role="button" tabindex="0" aria-label="Abrir ${monthName} no gráfico"><div><span>${monthName}</span><em>${status}</em></div><strong>${formatMoney(month.revenue)}</strong><small>Meta: ${formatMoney(goal)} · ${Math.round(month.revenue / goal * 100)}%</small><div class="goal-month-progress"><i style="width:${progress}%"></i></div><p>${detail}</p></article>`;
    }).join("");
  } catch (error) { target.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`; }
  finally { button.disabled = false; }
}

async function saveBusinessSettings(event) {
  event.preventDefault(); $("business-error").textContent = ""; $("save-business").disabled = true; $("save-business-label").textContent = "Salvando...";
  try {
    state.business = await request(`/businesses/${state.me.business_id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(businessUpdatePayload()) });
    $("business-name").textContent = state.business.name;
    await loadAgenda();
    await loadHome();
    document.querySelector('.nav-item[data-view="inicio"]').click();
    window.scrollTo({ top: 0, behavior: "smooth" });
    showToast("Informações salvas com sucesso.");
  } catch (error) { $("business-error").textContent = error.message; }
  finally { $("save-business").disabled = false; $("save-business-label").textContent = "Salvar configurações"; }
}

async function saveLoyaltySettings(event) {
  event.preventDefault(); $("loyalty-error").textContent = ""; $("save-loyalty").disabled = true; $("save-loyalty-label").textContent = "Salvando...";
  try {
    state.business = await request(`/businesses/${state.me.business_id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(businessUpdatePayload()) });
    await loadCustomerPortfolio(); showToast("Programa de fidelidade atualizado.");
  } catch (error) { $("loyalty-error").textContent = error.message; }
  finally { $("save-loyalty").disabled = false; $("save-loyalty-label").textContent = "Salvar fidelidade"; }
}

async function changeOwnerPassword(event) {
  event.preventDefault(); const currentPassword = $("current-password").value; const newPassword = $("new-password").value; const confirmation = $("confirm-password").value;
  $("password-error").textContent = "";
  if (newPassword !== confirmation) { $("password-error").textContent = "A confirmação não corresponde à nova senha."; return; }
  if (currentPassword === newPassword) { $("password-error").textContent = "A nova senha deve ser diferente da senha atual."; return; }
  $("save-password").disabled = true; $("save-password-label").textContent = "Alterando...";
  try {
    await request("/auth/password", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) });
    $("password-form").reset(); showToast("Senha alterada. Entre novamente com a nova senha."); setTimeout(logout, 1500);
  } catch (error) { $("password-error").textContent = error.message.includes("Current password") ? "A senha atual está incorreta." : error.message; }
  finally { $("save-password").disabled = false; $("save-password-label").textContent = "Alterar senha"; }
}

async function changeOwnerEmail(event) {
  event.preventDefault(); const newEmail = $("new-email").value.trim().toLowerCase(); $("email-error").textContent = "";
  if (newEmail === state.me.email.toLowerCase()) { $("email-error").textContent = "Informe um e-mail diferente do atual."; return; }
  $("save-email").disabled = true; $("save-email-label").textContent = "Enviando...";
  try {
    const result = await request("/auth/email/request", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ current_password: $("email-current-password").value, new_email: newEmail }) });
    state.pendingEmail = newEmail; $("email-code-destination").textContent = `Enviado para ${newEmail}`; $("email-code-hint").textContent = result.development_code ? `Modo de desenvolvimento — código: ${result.development_code}` : "O código expira em 10 minutos."; $("email-code").value = ""; $("email-confirm-error").textContent = ""; $("email-confirm-modal").hidden = false; document.body.classList.add("modal-open"); setTimeout(() => $("email-code").focus(), 0);
  } catch (error) { $("email-error").textContent = error.message.includes("Current password") ? "A senha atual está incorreta." : error.message.includes("already exists") ? "Este e-mail já está sendo utilizado." : error.message.includes("could not be sent") ? "Não foi possível enviar o e-mail de confirmação." : error.message; }
  finally { $("save-email").disabled = false; $("save-email-label").textContent = "Enviar código"; }
}

function closeEmailConfirmation() { $("email-confirm-modal").hidden = true; document.body.classList.remove("modal-open"); }

async function confirmOwnerEmail(event) {
  event.preventDefault(); $("email-confirm-error").textContent = ""; $("confirm-email").disabled = true; $("confirm-email-label").textContent = "Confirmando...";
  try {
    const updated = await request("/auth/email/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: $("email-code").value.trim() }) });
    state.me = updated; closeEmailConfirmation(); $("email-form").reset(); $("current-email").value = updated.email; showToast("E-mail confirmado. Entre novamente com o novo endereço."); setTimeout(logout, 1500);
  } catch (error) { $("email-confirm-error").textContent = error.message.includes("invalid or expired") ? "O código é inválido ou expirou." : error.message; }
  finally { $("confirm-email").disabled = false; $("confirm-email-label").textContent = "Confirmar novo e-mail"; }
}

$("login-form").addEventListener("submit", login); $("logout").addEventListener("click", logout); $("logout-header").addEventListener("click", logout); $("refresh").addEventListener("click", loadAgenda); $("date-filter").addEventListener("change", loadAgenda); $("barber-filter").addEventListener("change", loadAgenda);
$("previous-day").addEventListener("click", () => moveAgendaDate(-1)); $("today-button").addEventListener("click", goToToday); $("next-day").addEventListener("click", () => moveAgendaDate(1));
$("agenda-search").addEventListener("input", () => renderAppointments(state.appointments)); $("agenda-status").addEventListener("change", () => renderAppointments(state.appointments));
$("new-appointment").addEventListener("click", openAppointmentModal); $("close-appointment").addEventListener("click", closeAppointmentModal); $("cancel-appointment-form").addEventListener("click", closeAppointmentModal); $("appointment-barber").addEventListener("change", loadBookingSlots); $("appointment-date").addEventListener("change", loadBookingSlots); $("appointment-service").addEventListener("change", renderBookingSlots); $("appointment-form").addEventListener("submit", createAppointment);
$("appointment-modal").addEventListener("click", (event) => { if (event.target === $("appointment-modal")) closeAppointmentModal(); }); document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !$("appointment-modal").hidden) closeAppointmentModal(); });
[$("reschedule-barber"), $("reschedule-service"), $("reschedule-date")].forEach((input) => input.addEventListener("change", loadRescheduleSlots)); $("reschedule-form").addEventListener("submit", rescheduleAppointment); $("close-reschedule").addEventListener("click", closeRescheduleModal); $("cancel-reschedule").addEventListener("click", closeRescheduleModal); $("reschedule-modal").addEventListener("click", (event) => { if (event.target === $("reschedule-modal")) closeRescheduleModal(); });
document.querySelectorAll(".open-person").forEach((button) => button.addEventListener("click", () => openPersonModal(button.dataset.kind))); $("close-person").addEventListener("click", closePersonModal); $("cancel-person").addEventListener("click", closePersonModal); $("person-form").addEventListener("submit", createPerson); $("person-modal").addEventListener("click", (event) => { if (event.target === $("person-modal")) closePersonModal(); }); document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !$("person-modal").hidden) closePersonModal(); });
$("customers").addEventListener("click", (event) => { const historyButton = event.target.closest("[data-history-id]"); if (historyButton) { openCustomerHistory(historyButton.dataset.historyId); return; } const whatsappButton = event.target.closest("[data-customer-whatsapp]"); if (whatsappButton) { inviteCustomerBack(whatsappButton.dataset.customerWhatsapp); return; } const editButton = event.target.closest("[data-edit-customer-id]"); if (editButton) openCustomerEditModal(editButton.dataset.editCustomerId); }); $("close-history").addEventListener("click", closeCustomerHistory); $("history-modal").addEventListener("click", (event) => { if (event.target === $("history-modal")) closeCustomerHistory(); });
$("customer-search").addEventListener("input", renderPeople);
$("export-customers").addEventListener("click", exportCustomers);
$("customer-ranking-list").addEventListener("click", (event) => { const button = event.target.closest("[data-ranking-history-id]"); if (button) openCustomerHistory(button.dataset.rankingHistoryId); });
$("birthday-list").addEventListener("click", (event) => { const button = event.target.closest("[data-birthday-whatsapp]"); if (button) sendBirthdayMessage(button.dataset.birthdayWhatsapp); });
$("history-loyalty").addEventListener("click", (event) => { const button = event.target.closest("[data-redeem-loyalty]"); if (button) redeemLoyaltyReward(button.dataset.redeemLoyalty); });
document.querySelectorAll("[data-customer-segment]").forEach((button) => button.addEventListener("click", () => { state.customerSegment = button.dataset.customerSegment; renderPeople(); }));
$("team").addEventListener("click", (event) => { const accessButton = event.target.closest("[data-barber-access-id]"); if (accessButton) { openBarberAccessModal(accessButton.dataset.barberAccessId); return; } const editButton = event.target.closest("[data-edit-barber-id]"); if (editButton) { openBarberEditModal(editButton.dataset.editBarberId); return; } const toggleButton = event.target.closest("[data-toggle-barber-id]"); if (toggleButton) { toggleBarber(toggleButton.dataset.toggleBarberId, toggleButton.dataset.active === "true"); return; } const timeOffButton = event.target.closest("[data-time-off-id]"); if (timeOffButton) { openTimeOffModal(timeOffButton.dataset.timeOffId); return; } const scheduleButton = event.target.closest("[data-schedule-id]"); if (scheduleButton) openScheduleModal(scheduleButton.dataset.scheduleId); }); $("close-schedule").addEventListener("click", closeScheduleModal); $("cancel-schedule").addEventListener("click", closeScheduleModal); $("schedule-form").addEventListener("submit", saveSchedule); $("schedule-modal").addEventListener("click", (event) => { if (event.target === $("schedule-modal")) closeScheduleModal(); });
$("barber-access-form").addEventListener("submit", createBarberAccess); $("close-barber-access").addEventListener("click", closeBarberAccessModal); $("cancel-barber-access").addEventListener("click", closeBarberAccessModal); $("barber-access-modal").addEventListener("click", (event) => { if (event.target === $("barber-access-modal")) closeBarberAccessModal(); });
$("custom-schedule").addEventListener("change", toggleCustomSchedule); document.querySelectorAll('input[name="weekday"]').forEach((input) => input.addEventListener("change", updateCustomScheduleRows));
$("close-time-off").addEventListener("click", closeTimeOffModal); $("time-off-form").addEventListener("submit", createTimeOff); $("time-off-list").addEventListener("click", (event) => { const button = event.target.closest("[data-delete-time-off]"); if (button) deleteTimeOff(button.dataset.deleteTimeOff); }); $("time-off-modal").addEventListener("click", (event) => { if (event.target === $("time-off-modal")) closeTimeOffModal(); });
$("new-service").addEventListener("click", openServiceModal); $("close-service").addEventListener("click", closeServiceModal); $("cancel-service").addEventListener("click", closeServiceModal); $("service-form").addEventListener("submit", createService); $("service-modal").addEventListener("click", (event) => { if (event.target === $("service-modal")) closeServiceModal(); }); $("services").addEventListener("click", (event) => { const editButton = event.target.closest("[data-service-edit]"); if (editButton) { openServiceEditModal(editButton.dataset.serviceEdit); return; } const toggleButton = event.target.closest("[data-service-toggle]"); if (toggleButton) toggleService(toggleButton.dataset.serviceToggle, toggleButton.dataset.active === "true"); });
$("close-payment").addEventListener("click", closePaymentModal); $("cancel-payment").addEventListener("click", closePaymentModal); $("payment-form").addEventListener("submit", completeAppointment); $("payment-modal").addEventListener("click", (event) => { if (event.target === $("payment-modal")) closePaymentModal(); });
$("refresh-report").addEventListener("click", loadFinancial);
$("export-report").addEventListener("click", exportFinancialReport);
$("chart-zoom-in").addEventListener("click", () => applyFinancialChartZoom(state.financialChartZoom + .5));
$("chart-zoom-out").addEventListener("click", () => applyFinancialChartZoom(state.financialChartZoom - .5));
$("chart-zoom-reset").addEventListener("click", () => applyFinancialChartZoom(1));
$("chart-period").addEventListener("change", () => { state.financialChartPeriod = $("chart-period").value; const labels = { day: "dia", week: "semana", month: "mês" }; $("financial-chart-subtitle").textContent = `Receitas, despesas e resultado líquido por ${labels[state.financialChartPeriod]}`; state.financialChartZoom = 1; $("financial-chart-viewport").scrollLeft = 0; renderFinancialChart(state.financialChartPoints); });
$("refresh-financial-chart").addEventListener("click", loadFinancialChartPeriod);
const chartViewport = $("financial-chart-viewport"); let chartDragStart = null;
chartViewport.addEventListener("pointerdown", (event) => { if (state.financialChartZoom === 1 || event.button !== 0) return; chartDragStart = { x: event.clientX, scroll: chartViewport.scrollLeft }; chartViewport.setPointerCapture(event.pointerId); chartViewport.classList.add("dragging"); });
chartViewport.addEventListener("pointermove", (event) => { if (!chartDragStart) return; chartViewport.scrollLeft = chartDragStart.scroll - (event.clientX - chartDragStart.x); });
chartViewport.addEventListener("pointerup", (event) => { if (!chartDragStart) return; chartDragStart = null; chartViewport.releasePointerCapture(event.pointerId); chartViewport.classList.remove("dragging"); });
chartViewport.addEventListener("pointercancel", () => { chartDragStart = null; chartViewport.classList.remove("dragging"); });
chartViewport.addEventListener("wheel", (event) => { if (!event.ctrlKey) return; event.preventDefault(); const rect = chartViewport.getBoundingClientRect(), focus = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)); applyFinancialChartZoom(state.financialChartZoom + (event.deltaY < 0 ? .5 : -.5), focus); }, { passive: false });
$("new-expense").addEventListener("click", openExpenseModal); $("close-expense").addEventListener("click", closeExpenseModal); $("cancel-expense").addEventListener("click", closeExpenseModal); $("expense-form").addEventListener("submit", createExpense); $("expense-modal").addEventListener("click", (event) => { if (event.target === $("expense-modal")) closeExpenseModal(); }); $("expenses").addEventListener("click", (event) => { const pendingButton = event.target.closest("[data-expense-pending]"); if (pendingButton) { markExpensePending(pendingButton.dataset.expensePending); return; } const paidButton = event.target.closest("[data-expense-paid]"); if (paidButton) { markExpensePaid(paidButton.dataset.expensePaid); return; } const editButton = event.target.closest("[data-expense-edit]"); if (editButton) { openExpenseEditModal(editButton.dataset.expenseEdit); return; } const deleteButton = event.target.closest("[data-expense-id]"); if (deleteButton) deleteExpense(deleteButton.dataset.expenseId); });
$("close-confirmation").addEventListener("click", () => closeConfirmation(false)); $("cancel-confirmation").addEventListener("click", () => closeConfirmation(false)); $("confirmation-submit").addEventListener("click", () => closeConfirmation(true)); $("confirmation-modal").addEventListener("click", (event) => { if (event.target === $("confirmation-modal")) closeConfirmation(false); }); document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !$("confirmation-modal").hidden) closeConfirmation(false); });
$("expense-filter").addEventListener("change", () => renderExpenses(state.expensePeriodItems));
$("refresh-expense-summary").addEventListener("click", loadExpensePeriod);
$("compare-expense-months").addEventListener("click", compareExpenseMonths);
$("expense-comparison-results").addEventListener("click", async (event) => { if (!event.target.closest("#copy-expense-analysis") || !state.expenseAnalysisText) return; try { await navigator.clipboard.writeText(state.expenseAnalysisText); showToast("Relatório copiado com sucesso."); } catch { showToast("Não foi possível copiar o relatório."); } });
$("expense-comparison-results").addEventListener("click", (event) => { if (event.target.closest("#print-expense-analysis")) printExpenseAnalysis(); });
document.querySelector(".expense-summary").addEventListener("click", (event) => { const card = event.target.closest("[data-expense-summary-filter]"); if (!card) return; $("expense-filter").value = card.dataset.expenseSummaryFilter; renderExpenses(state.expensePeriodItems); document.querySelector(".expense-card").scrollIntoView({ behavior: "smooth", block: "start" }); });
document.querySelector(".expense-summary").addEventListener("keydown", (event) => { if (!["Enter", " "].includes(event.key)) return; const card = event.target.closest("[data-expense-summary-filter]"); if (!card) return; event.preventDefault(); card.click(); });
$("generate-fixed-expenses").addEventListener("click", generateFixedExpenses);
[$("report-from"), $("report-to")].forEach((input) => input.addEventListener("change", () => { state.financialReport = null; $("export-report").disabled = true; }));
$("appointments").addEventListener("click", (event) => { const detail = event.target.closest("[data-detail-id]"); if (detail) { openAppointmentDetail(detail.dataset.detailId); return; } const reschedule = event.target.closest("[data-reschedule-id]"); if (reschedule) { openRescheduleModal(reschedule.dataset.rescheduleId); return; } const reminder = event.target.closest("[data-reminder-id]"); if (reminder) { sendWhatsAppReminder(reminder.dataset.reminderId); return; } const complete = event.target.closest("[data-complete-id]"); if (complete) { openPaymentModal(complete.dataset.completeId); return; } const button = event.target.closest("button[data-action]"); if (button) changeStatus(button.dataset.action, button.dataset.id); });
$("close-appointment-detail").addEventListener("click", closeAppointmentDetail); $("appointment-detail-modal").addEventListener("click", (event) => { if (event.target === $("appointment-detail-modal")) closeAppointmentDetail(); }); $("appointment-detail-whatsapp").addEventListener("click", () => window.open(`https://wa.me/${normalizeWhatsAppPhone($("appointment-detail-whatsapp").dataset.phone)}`, "_blank", "noopener")); $("save-appointment-notes").addEventListener("click", saveAppointmentNotes);
document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => { document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active")); button.classList.add("active"); document.querySelectorAll(".panel-view").forEach((p) => p.hidden = true); $(`${button.dataset.view}-panel`).hidden = false; document.querySelector("aside").classList.remove("open"); refreshActiveView(); }));
document.querySelectorAll("[data-home-view]").forEach((button) => button.addEventListener("click", () => document.querySelector(`.nav-item[data-view="${button.dataset.homeView}"]`).click()));
document.querySelector("[data-home-action='appointment']").addEventListener("click", () => { document.querySelector('.nav-item[data-view="agenda"]').click(); openAppointmentModal(); });
$("home-alert-list").addEventListener("click", (event) => { const paidButton = event.target.closest("[data-expense-paid]"); if (paidButton) { markExpensePaid(paidButton.dataset.expensePaid); return; } const alert = event.target.closest("[data-alert-view]"); if (alert) document.querySelector(`.nav-item[data-view="${alert.dataset.alertView}"]`).click(); });
$("menu").addEventListener("click", () => document.querySelector("aside").classList.toggle("open"));
$("copy-booking-link").addEventListener("click", async () => { try { await navigator.clipboard.writeText($("public-booking-link").value); showToast("Link copiado. Agora é só compartilhar!"); } catch { $("public-booking-link").select(); document.execCommand("copy"); showToast("Link copiado."); } });
$("business-form").addEventListener("submit", saveBusinessSettings);
$("loyalty-form").addEventListener("submit", saveLoyaltySettings);
$("revenue-goal-form").addEventListener("submit", saveRevenueGoal);
$("refresh-goal-history").addEventListener("click", loadRevenueGoalHistory);
$("goal-month-cards").addEventListener("click", async (event) => { const card = event.target.closest("[data-goal-month]"); if (!card) return; document.querySelectorAll("[data-goal-month]").forEach((item) => item.classList.toggle("selected", item === card)); const [year, month] = card.dataset.goalMonth.split("-").map(Number), lastDay = new Date(year, month, 0).getDate(); $("chart-date-from").value = `${card.dataset.goalMonth}-01`; $("chart-date-to").value = `${card.dataset.goalMonth}-${String(lastDay).padStart(2, "0")}`; $("chart-period").value = "day"; state.financialChartPeriod = "day"; $("financial-chart-subtitle").textContent = "Receitas, despesas e resultado líquido por dia"; const report = await loadFinancialChartPeriod(); renderGoalMonthAnalysis(report, card.dataset.goalMonth); $("goal-month-analysis").scrollIntoView({ behavior: "smooth", block: "nearest" }); });
$("goal-month-cards").addEventListener("keydown", (event) => { if (!["Enter", " "].includes(event.key)) return; const card = event.target.closest("[data-goal-month]"); if (!card) return; event.preventDefault(); card.click(); });
$("goal-month-analysis").addEventListener("click", async (event) => { if (event.target.closest("#print-goal-analysis")) { printGoalMonthAnalysis(); return; } if (!event.target.closest("#copy-goal-analysis")) return; const clone = $("goal-month-analysis").cloneNode(true); clone.querySelectorAll("button").forEach((button) => button.remove()); try { await navigator.clipboard.writeText(clone.innerText); showToast("Análise mensal copiada."); } catch { showToast("Não foi possível copiar a análise."); } });
$("password-form").addEventListener("submit", changeOwnerPassword);
$("email-form").addEventListener("submit", changeOwnerEmail);
$("email-confirm-form").addEventListener("submit", confirmOwnerEmail); $("close-email-confirm").addEventListener("click", closeEmailConfirmation); $("cancel-email-confirm").addEventListener("click", closeEmailConfirmation); $("email-confirm-modal").addEventListener("click", (event) => { if (event.target === $("email-confirm-modal")) closeEmailConfirmation(); });
$("closure-form").addEventListener("submit", createClosure); $("closure-list").addEventListener("click", (event) => { const button = event.target.closest("[data-closure-delete]"); if (button) deleteClosure(button.dataset.closureDelete); });
$("date-filter").value = localDate(); $("today-label").textContent = new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "2-digit", month: "long" }).format(new Date());
const today = localDate();
$("goal-history-year").value = today.slice(0, 4);
const reportMonthDays = new Date(Number(today.slice(0, 4)), Number(today.slice(5, 7)), 0).getDate();
$("report-from").value = `${today.slice(0, 8)}01`;
$("report-to").value = `${today.slice(0, 8)}${String(reportMonthDays).padStart(2, "0")}`;
$("chart-date-from").value = `${today.slice(0, 8)}01`;
$("chart-date-to").value = `${today.slice(0, 8)}${String(reportMonthDays).padStart(2, "0")}`;
$("expense-summary-from").value = `${today.slice(0, 8)}01`;
$("expense-summary-to").value = `${today.slice(0, 8)}${String(reportMonthDays).padStart(2, "0")}`;
$("comparison-month-b").value = today.slice(0, 7);
const previousMonth = new Date(Date.UTC(Number(today.slice(0, 4)), Number(today.slice(5, 7)) - 6, 1));
$("comparison-month-a").value = previousMonth.toISOString().slice(0, 7);
$("export-report").textContent = "Exportar Excel";
window.setInterval(refreshActiveView, 30000);
window.addEventListener("focus", refreshActiveView);
document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshActiveView(); });
if (state.token) boot();
