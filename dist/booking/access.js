/* WhatsApp recovery uses only the server-verified result, never a phone lookup. */
(() => {
  let challenge = null;
  let phone = "";
  let resendAt = 0;
  let expiresAt = 0;
  let sending = false;
  const message = text => { $("access-message").textContent = text; };
  const updateTimer = () => {
    const seconds = Math.max(0, Math.ceil((resendAt - Date.now()) / 1000));
    $("access-send").disabled = sending || seconds > 0;
    $("access-send").firstElementChild.textContent = seconds ? `Reenviar em ${seconds}s` : challenge ? "Reenviar código" : "Receber código no WhatsApp";
    if (challenge) {
      const remaining = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
      $("access-expiry").textContent = remaining ? `Código válido por ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}. Não compartilhe com ninguém.` : "O código expirou. Solicite um novo código.";
    }
  };
  setInterval(updateTimer, 1000);
  async function accessRequest(action, payload) {
    const response = await fetch(`${API}/public/businesses/${businessId}/access/${action}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 429) {
        resendAt = Date.now() + Math.max(1, Number(response.headers.get("Retry-After")) || 60) * 1000;
        updateTimer();
      }
      throw new Error(typeof data.detail === "string" ? data.detail : "Confira o WhatsApp com DDD e os dados informados.");
    }
    return data;
  }
  $("access-request-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (sending || Date.now() < resendAt) return;
    sending = true; updateTimer(); message("Solicitando seu código...");
    $("access-results").replaceChildren();
    try {
      phone = $("access-phone").value.trim();
      const result = await accessRequest("request", { phone, consent: $("access-consent").checked });
      challenge = result.challenge_id;
      resendAt = Date.now() + result.resend_after * 1000;
      expiresAt = Date.now() + result.expires_in * 1000;
      $("access-phone").readOnly = true;
      $("access-verify-form").hidden = false;
      $("access-code").value = "";
      $("access-code").focus();
      message("Solicitação enviada ao WhatsApp. Digite o código recebido para consultar suas reservas.");
    } catch (error) { message(error.message); }
    finally { sending = false; updateTimer(); }
  });
  $("access-change-phone").addEventListener("click", () => {
    challenge = null;
    $("access-phone").readOnly = false;
    $("access-verify-form").hidden = true;
    $("access-code").value = "";
    message(""); $("access-phone").focus(); updateTimer();
  });
  $("access-verify-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (!challenge) return;
    $("access-verify").disabled = true;
    try {
      const result = await accessRequest("verify", { phone, challenge_id: challenge, code: $("access-code").value.trim() });
      challenge = null;
      $("access-verify-form").hidden = true;
      $("access-code").value = "";
      $("access-phone").readOnly = false;
      const list = $("access-results");
      list.replaceChildren();
      for (const booking of result.bookings) {
        rememberBooking(booking.booking_token, booking);
        const button = document.createElement("button");
        button.type = "button"; button.className = "saved-booking";
        button.textContent = `${booking.service_name} · ${new Date(booking.starts_at).toLocaleString("pt-BR", { timeZone: state.business.timezone })} · Ver reserva →`;
        button.addEventListener("click", async () => {
          bookingToken = booking.booking_token;
          await loadManagedBooking();
          $("manage").scrollIntoView({ behavior: "smooth", block: "start" });
        });
        list.append(button);
      }
      renderSavedBookings();
      message(result.bookings.length ? "WhatsApp verificado! Escolha a reserva que deseja consultar." : "WhatsApp verificado. Não há reservas futuras ativas para este número nesta barbearia.");
    } catch (error) { message(error.message); }
    finally { $("access-verify").disabled = false; updateTimer(); }
  });
})();
