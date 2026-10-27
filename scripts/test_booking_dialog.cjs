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
      const errors = [];
      let cancellationRequests = 0;
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
        throw new Error(`Unexpected test request: ${pathname}`);
      });

      await page.goto('http://osiris.test/dashboard/booking/?business_id=test-business');
      await page.locator('#booking-card').waitFor({ state: 'visible' });
      await page.locator('#booking-confirmation').waitFor({ state: 'hidden' });
      await page.locator('#customer-fields').waitFor({ state: 'visible' });
      await page.locator('#success').waitFor({ state: 'hidden' });

      await page.goto('http://osiris.test/dashboard/booking/?booking_token=test-token');
      await page.locator('#manage').waitFor({ state: 'visible' });
      await page.locator('#booking-confirmation').waitFor({ state: 'hidden' });
      assert.equal(cancellationRequests, 0);
      for (const closeButton of ['#back-booking-confirmation', '#close-booking-confirmation']) {
        await page.locator('#cancel-booking').click();
        await page.locator('#booking-confirmation').waitFor({ state: 'visible' });
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
