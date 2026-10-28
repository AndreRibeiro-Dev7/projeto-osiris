// Restricted professional dashboard: every API interaction is intercepted locally.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');

for (const width of [375, 768, 1280]) {
  test(`restricted barber agenda at ${width}px`, async () => {
    const browser = await chromium.launch({ headless: true,
      ...(process.env.OSIRIS_BROWSER_CHANNEL ? { channel: process.env.OSIRIS_BROWSER_CHANNEL } : {}),
    });
    try {
      const page = await browser.newPage({ viewport: { width, height: 812 }, reducedMotion: 'reduce' });
      const errors = [];
      const requests = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.clock.install({ time: new Date('2026-10-27T15:00:00Z') });
      await page.addInitScript(() => sessionStorage.setItem('osiris_token', 'barber.mock.signature'));
      const me = { id: 'barber-user', business_id: 'business', barber_id: 'barber', email: 'profissional.de.demonstracao@example.com', role: 'barber', is_primary_owner: false };
      const profile = { business_id: 'business', business_name: 'Barbearia de demonstração com nome extenso', timezone: 'America/Sao_Paulo', barber_id: 'barber', full_name: 'Profissional de demonstração com nome completo', phone: '11999999999', commission_percentage: 50 };
      const appointment = { id: 'first', public_token: 'test-public-token', customer_id: 'customer', service_id: 'service', customer_name: 'Cliente com nome e sobrenome de demonstração', customer_phone: '11999999999', service_name: 'Corte e barba com acabamento especial', starts_at: '2026-10-27T16:00:00Z', ends_at: '2026-10-27T16:45:00Z', status: 'scheduled', price_cents: 6000, payment_method: null, notes: 'Observação cadastrada pelo proprietário.' };
      const second = { ...appointment, id: 'second', starts_at: '2026-10-27T17:00:00Z', ends_at: '2026-10-27T17:45:00Z' };
      let failPayment = true;
      let expired = false;
      await page.route('http://osiris.test/**', async route => {
        const request = route.request();
        const pathname = new URL(request.url()).pathname;
        if (pathname.startsWith('/dashboard/')) {
          const filename = pathname.split('/').pop() || 'index.html';
          assert.ok(['index.html', 'styles.css', 'app.js', 'favicon.svg'].includes(filename));
          return route.fulfill({ path: path.join(__dirname, '../dist', filename) });
        }
        requests.push({ method: request.method(), path: pathname });
        if (expired) return route.fulfill({ status: 401, json: { detail: 'Invalid or expired access token.' } });
        if (pathname === '/api/v1/auth/me') return route.fulfill({ json: me });
        if (pathname === '/api/v1/auth/barber/profile') return route.fulfill({ json: profile });
        if (pathname === '/api/v1/auth/barber/appointments') return route.fulfill({ json: [appointment, second] });
        assert.equal(request.method(), 'PATCH');
        if (pathname === '/api/v1/auth/barber/appointments/first/confirm') {
          appointment.status = 'confirmed';
          return route.fulfill({ json: appointment });
        }
        if (pathname === '/api/v1/auth/barber/appointments/first/complete') {
          assert.deepEqual(request.postDataJSON(), { payment_method: 'pix' });
          if (failPayment) return route.fulfill({ status: 503, json: { detail: 'Falha simulada. Tente novamente.' } });
          appointment.status = 'completed'; appointment.payment_method = 'pix';
          return route.fulfill({ json: appointment });
        }
        if (pathname === '/api/v1/auth/barber/appointments/second/no-show') {
          second.status = 'no_show';
          return route.fulfill({ json: second });
        }
        throw new Error(`Forbidden or unexpected professional UI request: ${pathname}`);
      });
      async function checkLayout(name) {
        const dimensions = await page.evaluate(() => ({ document: document.documentElement.scrollWidth, viewport: innerWidth }));
        if (process.env.OSIRIS_SCREENSHOTS || dimensions.document > dimensions.viewport + 1) {
          await page.screenshot({ path: `work/barber-${width}-${name}.png`, fullPage: true, animations: 'disabled' });
        }
        assert.ok(dimensions.document <= dimensions.viewport + 1, `${name} must fit the viewport`);
      }
      await page.goto('http://osiris.test/dashboard/');
      await page.locator('#schedule-count').filter({ hasText: '2 atendimentos' }).waitFor();
      assert.equal(await page.locator('.nav-item:not([hidden])').count(), 1);
      assert.equal(await page.locator('.nav-item:not([hidden])').getAttribute('data-view'), 'agenda');
      assert.equal(await page.locator('.panel-view:visible').getAttribute('id'), 'agenda-panel');
      assert.equal(await page.locator('#open-account-security').isHidden(), true);
      assert.equal(await page.locator('#new-appointment').isHidden(), true);
      assert.equal(await page.locator('#barber-filter').isDisabled(), true);
      assert.equal(await page.locator('#appointments [data-reschedule-id], #appointments [data-action="cancel"]').count(), 0);
      await checkLayout('agenda');

      await page.locator('[data-detail-id="first"]').click();
      await page.locator('#appointment-detail-modal').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#appointment-detail-title').textContent(), appointment.customer_name);
      assert.match(await page.locator('#appointment-detail-content').textContent(), /Corte e barba/);
      assert.equal(await page.locator('#save-appointment-notes').isHidden(), true);
      assert.equal(await page.locator('#appointment-detail-notes').getAttribute('readonly'), '');
      await checkLayout('details');
      await page.locator('#close-appointment-detail').click();
      await page.locator('[data-action="confirm"][data-id="first"]').click();
      await page.locator('#stat-confirmed').filter({ hasText: '1' }).waitFor();
      await page.locator('[data-complete-id="first"]').click();
      await page.locator('#payment-modal').waitFor({ state: 'visible' });
      await page.locator('#payment-method').selectOption('pix');
      await checkLayout('payment');
      await page.locator('#save-payment').click();
      await page.locator('#payment-error').filter({ hasText: 'Falha simulada' }).waitFor();
      assert.equal(await page.locator('#payment-modal').isVisible(), true);
      assert.equal(await page.locator('#save-payment').isDisabled(), false);
      failPayment = false;
      await page.locator('#save-payment').click();
      await page.locator('#payment-modal').waitFor({ state: 'hidden' });
      await page.locator('[data-complete-id="first"]').waitFor({ state: 'detached' });
      assert.match(await page.locator('#stat-revenue').textContent(), /60,00/);
      await page.locator('[data-action="no-show"][data-id="second"]').click();
      await page.locator('[data-action="no-show"][data-id="second"]').waitFor({ state: 'detached' });
      assert.ok(requests.every(item => item.path === '/api/v1/auth/me' || item.path.startsWith('/api/v1/auth/barber/')));

      expired = true;
      await page.locator('#refresh').click();
      await page.locator('#login-view').waitFor({ state: 'visible' });
      assert.equal(await page.evaluate(() => sessionStorage.getItem('osiris_token')), null);
      expired = false;
      await page.reload();
      await page.locator('#app-view').waitFor({ state: 'visible' });
      if (width <= 760) {
        await page.locator('#menu').click();
        await page.locator('#logout').click();
      } else await page.locator('#logout-header').click();
      await page.locator('#login-view').waitFor({ state: 'visible' });
      assert.equal(await page.evaluate(() => sessionStorage.getItem('osiris_token')), null);
      assert.equal(await page.locator('#menu').getAttribute('aria-expanded'), 'false');
      assert.deepEqual(errors, []);
    } finally { await browser.close(); }
  });
}
