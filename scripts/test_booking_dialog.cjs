// Run with: node --test scripts/test_booking_dialog.cjs (requires playwright).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');

for (const viewport of [{ width: 375, height: 812 }, { width: 1280, height: 900 }]) {
  test(`public booking cancellation dialog at ${viewport.width}px`, async () => {
    const browser = await chromium.launch({
      headless: true,
      ...(process.env.OSIRIS_BROWSER_CHANNEL ? { channel: process.env.OSIRIS_BROWSER_CHANNEL } : {}),
    });
    try {
      const page = await browser.newPage({ viewport });
      await page.clock.install({ time: new Date('2026-10-27T14:14:00Z') });
      const errors = [];
      let cancellationRequests = 0;
      let bookingRequests = 0;
      page.on('pageerror', error => errors.push(error.message));
      const summary = {
        business_id: 'test-business', business_name: 'Test business',
        service_name: 'Test service', barber_name: 'Test barber',
        starts_at: '2030-01-17T09:00:00-03:00', status: 'scheduled',
      };
      await page.route('http://osiris.test/**', async route => {
        const request = route.request();
        const pathname = new URL(request.url()).pathname;
        if (pathname.startsWith('/dashboard/booking/')) {
          const filename = pathname.split('/').pop() || 'index.html';
          assert.ok(['index.html', 'booking.css', 'manage.css', 'booking.js'].includes(filename));
          return route.fulfill({ path: path.join(__dirname, '../dist/booking', filename) });
        }
        if (pathname === '/api/v1/public/businesses/appointments/test-token/cancel') {
          assert.equal(request.method(), 'PATCH');
          cancellationRequests++;
          return route.fulfill({ json: { ...summary, status: 'cancelled' } });
        }
        if (pathname === '/api/v1/public/businesses/appointments/test-token') {
          return route.fulfill({ json: summary });
        }
        if (pathname === '/api/v1/public/businesses/test-business') {
          return route.fulfill({ json: {
            id: 'test-business', name: 'Test business', timezone: 'America/Sao_Paulo',
            services: [{ id: 'service', name: 'Test service', duration_minutes: 30, price_cents: 2500 }],
            barbers: [{ id: 'barber', full_name: 'Test barber' }],
          } });
        }
        if (pathname === '/api/v1/public/businesses/test-business/appointments') {
          assert.equal(request.method(), 'POST');
          assert.deepEqual(request.postDataJSON(), {
            barber_id: 'barber', service_id: 'service',
            starts_at: '2026-10-27T11:30:00-03:00',
            customer_name: 'Cliente de teste', customer_phone: '11999999999', notes: null,
          });
          bookingRequests++;
          return route.fulfill({ json: { ...summary, starts_at: '2026-10-27T11:30:00-03:00', booking_token: 'test-token' } });
        }
        if (pathname.endsWith('/availability')) {
          return route.fulfill({ json: { slots: [
            { starts_at: '2026-10-27T10:30:00-03:00', ends_at: '2026-10-27T11:00:00-03:00' },
            { starts_at: '2026-10-27T11:00:00-03:00', ends_at: '2026-10-27T11:30:00-03:00' },
            { starts_at: '2026-10-27T11:30:00-03:00', ends_at: '2026-10-27T12:00:00-03:00' },
          ] } });
        }
        throw new Error(`Unexpected test request: ${pathname}`);
      });

      await page.goto('http://osiris.test/dashboard/booking/?business_id=test-business');
      await page.locator('#booking-card').waitFor({ state: 'visible' });
      await page.locator('#booking-confirmation').waitFor({ state: 'hidden' });
      await page.locator('#customer-fields').waitFor({ state: 'visible' });
      await page.locator('#success').waitFor({ state: 'hidden' });
      await page.locator('#service').selectOption('service');
      await page.locator('#barber').selectOption('barber');
      await page.getByRole('button', { name: '11:30', exact: true }).waitFor();
      assert.equal(await page.locator('.slot').count(), 1);
      await page.getByRole('button', { name: '11:30', exact: true }).click();
      assert.equal(await page.locator('#submit').isDisabled(), false);
      assert.equal(await page.locator('#summary-service').textContent(), 'Test service');
      assert.equal(await page.locator('#summary-barber').textContent(), 'Test barber');
      assert.match(await page.locator('#summary-price').textContent(), /25,00/);
      assert.match(await page.locator('#summary-when').textContent(), /11:30/);
      assert.equal(await page.locator('.slot.selected').getAttribute('aria-pressed'), 'true');
      assert.equal(await page.locator('.steps [aria-current="step"]').textContent(), '03Reserva');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      if (process.env.OSIRIS_SCREENSHOTS) {
        await page.screenshot({ path: `work/booking-${viewport.width}.png`, fullPage: true });
      }
      await page.locator('#barber').selectOption('');
      assert.equal(await page.locator('#submit').isDisabled(), true);
      assert.equal(await page.locator('#summary-when').textContent(), 'Selecione um horário');
      assert.equal(await page.locator('.slot').count(), 0);
      await page.locator('#barber').selectOption('barber');
      await page.getByRole('button', { name: '11:30', exact: true }).click();
      await page.clock.fastForward(17 * 60 * 1000);
      await page.waitForFunction(() => document.querySelectorAll('.slot').length === 0);
      assert.equal(await page.locator('#submit').isDisabled(), true);
      assert.match(await page.locator('#error').textContent(), /já passou/);
      assert.equal(await page.locator('#summary-when').textContent(), 'Selecione um horário');

      await page.clock.setSystemTime(new Date('2026-10-27T14:14:00Z'));
      await page.reload();
      await page.locator('#service').selectOption('service');
      await page.locator('#barber').selectOption('barber');
      await page.getByRole('button', { name: '11:30', exact: true }).click();
      await page.locator('#name').fill('Cliente de teste');
      await page.locator('#phone').fill('11999999999');
      await page.locator('#submit').click();
      await page.locator('#success').waitFor({ state: 'visible' });
      assert.equal(bookingRequests, 1);
      assert.match(await page.locator('#success-detail').textContent(), /11:30/);
      assert.match(await page.locator('#cancellation-link').inputValue(), /booking_token=test-token/);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);

      await page.goto('http://osiris.test/dashboard/booking/?booking_token=test-token');
      await page.locator('#manage').waitFor({ state: 'visible' });
      await page.locator('#booking-confirmation').waitFor({ state: 'hidden' });
      assert.equal(cancellationRequests, 0);
      for (const closeButton of ['#back-booking-confirmation', '#close-booking-confirmation']) {
        await page.locator('#cancel-booking').click();
        await page.locator('#booking-confirmation').waitFor({ state: 'visible' });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        await page.locator(closeButton).click();
        await page.locator('#booking-confirmation').waitFor({ state: 'hidden' });
        assert.equal(cancellationRequests, 0);
      }
      await page.locator('#cancel-booking').click();
      await page.locator('#booking-confirmation').waitFor({ state: 'visible' });
      await page.keyboard.press('Escape');
      await page.locator('#booking-confirmation').waitFor({ state: 'hidden' });
      assert.equal(cancellationRequests, 0);

      await page.locator('#cancel-booking').click();
      await page.locator('#submit-booking-confirmation').click();
      await page.locator('#manage-title').filter({ hasText: 'Agendamento cancelado' }).waitFor();
      await page.locator('#booking-confirmation').waitFor({ state: 'hidden' });
      await page.locator('#cancel-booking').waitFor({ state: 'hidden' });
      assert.equal(cancellationRequests, 1);
      assert.deepEqual(errors, []);
    } finally {
      await browser.close();
    }
  });
}
