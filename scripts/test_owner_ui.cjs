// Responsive owner dashboard smoke test with local assets and a read-only mocked API.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');

for (const viewport of [{ width: 375, height: 812 }, { width: 768, height: 1024 }, { width: 1280, height: 900 }, { width: 768, height: 1024, font: 'Arial', gutter: true }]) {
  test(`owner navigation and forms at ${viewport.width}px${viewport.font ? ' with fallback font' : ''}`, async () => {
    const browser = await chromium.launch({ headless: true,
      ...(process.env.OSIRIS_BROWSER_CHANNEL ? { channel: process.env.OSIRIS_BROWSER_CHANNEL } : {}),
    });
    try {
      const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height }, reducedMotion: 'reduce' });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.clock.install({ time: new Date('2026-10-27T15:00:00Z') });
      await page.addInitScript(() => sessionStorage.setItem('osiris_token', 'test.mock.signature'));
      const business = { id: 'business', name: 'Barbearia Osiris de demonstração', phone: '11999999999', timezone: 'America/Sao_Paulo', loyalty_enabled: true, loyalty_target: 10, loyalty_reward: 'Um corte de cortesia', monthly_revenue_goal_cents: 50000 };
      const me = { id: 'owner', business_id: 'business', email: 'proprietario.principal.de.demonstracao@example.com', role: 'owner', is_primary_owner: true, is_active: true };
      const barber = { id: 'barber', full_name: 'Profissional de demonstração com nome completo', phone: '11999999999', commission_percentage: 50, is_active: true };
      const customer = { id: 'customer', full_name: 'Cliente de demonstração com sobrenome extenso', phone: '11999999999', notes: '', birth_date: null };
      const service = { id: 'service', name: 'Corte, barba e acabamento especial', duration_minutes: 45, price_cents: 6000, is_active: true };
      const appointment = { id: 'appointment', public_token: 'public-token', customer_id: 'customer', barber_id: 'barber', service_id: 'service', starts_at: '2026-10-27T16:00:00Z', ends_at: '2026-10-27T16:45:00Z', status: 'confirmed', price_cents: 6000, notes: null };
      const expense = { id: 'expense', category: 'rent', description: 'Aluguel e despesas de manutenção do espaço', amount_cents: 240000, occurred_on: '2026-10-05', is_fixed: true, is_paid: false, paid_at: null };
      await page.route('http://osiris.test/**', async route => {
        const request = route.request();
        const url = new URL(request.url());
        const pathname = url.pathname;
        if (pathname.startsWith('/dashboard/')) {
          const filename = pathname.split('/').pop() || 'index.html';
          assert.ok(['index.html', 'styles.css', 'app.js', 'favicon.svg'].includes(filename));
          return route.fulfill({ path: path.join(__dirname, '../dist', filename) });
        }
        assert.equal(request.method(), 'GET', 'This smoke test must never mutate data');
        let data;
        if (pathname === '/api/v1/auth/me') data = me;
        else if (pathname === '/api/v1/auth/owner-accounts') data = [me];
        else if (pathname === '/api/v1/auth/barber-accounts') data = [];
        else if (pathname === '/api/v1/businesses/business') data = business;
        else if (pathname.endsWith('/customers/portfolio')) data = [];
        else if (pathname.endsWith('/barbers')) data = [barber];
        else if (pathname.endsWith('/customers')) data = [customer];
        else if (pathname.endsWith('/services')) data = [service];
        else if (pathname.endsWith('/appointments')) data = [appointment];
        else if (pathname.endsWith('/availability')) data = { slots: [{ starts_at: '2026-10-27T17:00:00Z', ends_at: '2026-10-27T17:30:00Z' }] };
        else if (pathname.endsWith('/expenses')) data = [expense];
        else if (pathname.endsWith('/closures') || pathname.endsWith('/audit-logs')) data = [];
        else if (pathname.endsWith('/reports/financial')) {
          data = { date_from: url.searchParams.get('date_from'), date_to: url.searchParams.get('date_to'), total_revenue_cents: 6000, total_commission_cents: 3000, net_revenue_cents: 3000, total_expenses_cents: 240000, final_result_cents: -237000, average_ticket_cents: 6000, attendance_rate_percent: 100, completed: 1, scheduled: 0, confirmed: 1, cancelled: 0, no_show: 0,
            by_barber: [{ id: 'barber', label: barber.full_name, total_cents: 6000, appointments: 1, commission_percentage: 50, commission_cents: 3000 }],
            by_service: [{ id: 'service', label: service.name, total_cents: 6000, appointments: 1 }],
            by_payment_method: [{ label: 'Pix', total_cents: 6000, appointments: 1 }], expenses: [expense],
            daily: [{ date: '2026-10-27', appointments: 1, revenue_cents: 6000, expense_cents: 240000, result_cents: -237000 }],
          };
        } else throw new Error(`Unexpected test request: ${pathname}`);
        return route.fulfill({ json: data });
      });
      await page.goto('http://osiris.test/dashboard/');
      const font = viewport.font || process.env.OSIRIS_UI_FONT;
      if (font) {
        await page.addStyleTag({ content: `body, .app-shell * { font-family: ${font}, sans-serif !important; }` });
      }
      if (viewport.gutter || process.env.OSIRIS_UI_GUTTER) {
        await page.addStyleTag({ content: 'html { scrollbar-gutter: stable; }' });
      }
      await page.locator('#app-view').waitFor({ state: 'visible' });
      await page.locator('#home-revenue').filter({ hasNotText: '—' }).waitFor();
      const overflow = [];
      async function checkLayout(name) {
        const size = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, viewport: innerWidth }));
        if (size.width > size.viewport + 1) {
          const offenders = await page.evaluate(() => Array.from(document.querySelectorAll('body *'))
            .filter(item => item.getBoundingClientRect().right > innerWidth + 1 && item.getBoundingClientRect().width > 0)
            .map(item => ({ tag: item.tagName, id: item.id, className: String(item.className), parent: item.parentElement?.id || item.parentElement?.className, text: item.textContent?.slice(0, 70), right: Math.round(item.getBoundingClientRect().right) })).slice(0, 12));
          overflow.push({ name, ...size, offenders });
        }
        const headerFits = await page.evaluate(() => {
          const header = document.querySelector('.workspace>header').getBoundingClientRect();
          return ['business-name', 'today-label'].every(id => {
            const child = document.getElementById(id).getBoundingClientRect();
            return child.top >= header.top && child.bottom <= header.bottom;
          });
        });
        assert.equal(headerFits, true, 'Business name and date must fit inside the header');
        if (process.env.OSIRIS_SCREENSHOTS || size.width > size.viewport + 1) {
          await page.screenshot({ path: `work/owner-${viewport.width}-${name}.png`, fullPage: true, animations: 'disabled' });
        }
      }
      async function navigate(view) {
        if (viewport.width <= 760) await page.locator('#menu').click();
        await page.locator(`.nav-item[data-view="${view}"]`).click();
        await page.locator(`#${view}-panel`).waitFor({ state: 'visible' });
        await page.waitForFunction(() => !state.refreshInFlight);
        if (viewport.width <= 760) {
          assert.equal(await page.locator('#menu').getAttribute('aria-expanded'), 'false');
          await page.waitForFunction(() => document.getElementById('app-sidebar').getBoundingClientRect().right <= 1);
        }
      }
      for (const view of ['inicio', 'agenda', 'clientes', 'equipe', 'servicos', 'financeiro', 'online', 'configuracoes', 'owner-accounts', 'atividades', 'fechamentos']) {
        await navigate(view);
        if (view === 'financeiro') await page.locator('#goal-month-cards article').first().waitFor();
        await checkLayout(view);
      }
      for (const [view, button, modal, close] of [
        ['agenda', '#new-appointment', '#appointment-modal', '#cancel-appointment-form'],
        ['financeiro', '#new-expense', '#expense-modal', '#cancel-expense'],
        ['clientes', '.open-person[data-kind="customer"]', '#person-modal', '#cancel-person'],
      ]) {
        await navigate(view);
        await page.locator(button).click();
        await page.locator(modal).waitFor({ state: 'visible' });
        await checkLayout(modal.slice(1));
        await page.locator(close).click();
        await page.locator(modal).waitFor({ state: 'hidden' });
      }
      await page.locator('#open-account-security').click();
      await page.locator('#account-security-modal').waitFor({ state: 'visible' });
      await checkLayout('account-security');
      await page.locator('#close-account-security').click();
      if (viewport.width <= 760) {
        await page.setViewportSize({ width: viewport.width, height: 480 });
        await page.locator('#menu').click();
        await page.waitForFunction(() => document.getElementById('app-sidebar').getBoundingClientRect().left >= -1);
        assert.equal(await page.locator('#app-sidebar>nav').evaluate(nav => nav.scrollHeight > nav.clientHeight), true);
        await page.locator('.nav-item[data-view="fechamentos"]').scrollIntoViewIfNeeded();
        const exit = await page.locator('#logout').boundingBox();
        assert.ok(exit && exit.y >= 0 && exit.y + exit.height <= 480);
        await page.locator('#logout').click();
      } else {
        await page.locator('#logout-header').click();
      }
      await page.locator('#login-view').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#menu').getAttribute('aria-expanded'), 'false');
      assert.equal(await page.evaluate(() => sessionStorage.getItem('osiris_token')), null);
      assert.deepEqual(errors, []);
      assert.deepEqual(overflow, [], 'Pages and modals must fit the viewport');
    } finally { await browser.close(); }
  });
}
