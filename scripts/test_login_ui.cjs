// Isolated browser tests: no real account, email, or production API is used.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');

for (const width of [375, 1280]) {
  test(`login lockout and password recovery at ${width}px`, async () => {
    const browser = await chromium.launch({ headless: true,
      ...(process.env.OSIRIS_BROWSER_CHANNEL ? { channel: process.env.OSIRIS_BROWSER_CHANNEL } : {}),
    });
    try {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      await page.clock.install({ time: new Date('2026-10-27T18:00:00Z') });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      let loginRequests = 0;
      let confirmationRequests = 0;
      let mailReady = false;
      await page.route('http://osiris.test/**', async route => {
        const request = route.request();
        const pathname = new URL(request.url()).pathname;
        if (pathname.startsWith('/dashboard/')) {
          const filename = pathname.split('/').pop() || 'index.html';
          assert.ok(['index.html', 'styles.css', 'app.js', 'favicon.svg'].includes(filename));
          return route.fulfill({ path: path.join(__dirname, '../dist', filename) });
        }
        if (pathname === '/api/v1/auth/token') {
          loginRequests++;
          if (loginRequests === 1) {
            return route.fulfill({ status: 429, headers: { 'Retry-After': '900' }, json: { detail: 'Locked' } });
          }
          return route.fulfill({ status: 401, json: { detail: 'Incorrect email or password.' } });
        }
        if (pathname === '/api/v1/auth/password-reset/request') {
          assert.equal(request.postDataJSON().email, 'test@example.com');
          return route.fulfill(mailReady
            ? { json: { detail: 'Generic recovery response', development_code: null, expires_in_seconds: 600 } }
            : { status: 503, json: { detail: 'O envio de e-mail não está configurado.' } });
        }
        if (pathname === '/api/v1/auth/password-reset/confirm') {
          confirmationRequests++;
          const payload = request.postDataJSON();
          assert.equal(payload.new_password, payload.password_confirmation);
          if (payload.code !== '222222') {
            return route.fulfill({ status: 400, json: { detail: 'The recovery code is invalid or expired.' } });
          }
          return route.fulfill({ status: 204 });
        }
        throw new Error(`Unexpected test request: ${pathname}`);
      });
      await page.goto('http://osiris.test/dashboard/');
      await page.locator('#email').fill('test@example.com');
      await page.locator('#password').fill('Fictitious-password-123!');
      await page.locator('#login-button').click();
      await page.locator('#login-error').filter({ hasText: '15:00' }).waitFor();
      assert.equal(await page.locator('#login-button').isDisabled(), true);
      await page.clock.fastForward(1000);
      assert.match(await page.locator('#login-error').textContent(), /14:59/);
      assert.equal(loginRequests, 1);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      if (process.env.OSIRIS_SCREENSHOTS) {
        await page.screenshot({ path: `work/login-lockout-${width}.png`, fullPage: true });
      }
      await page.clock.fastForward(899000);
      assert.equal(await page.locator('#login-button').isDisabled(), false);
      assert.match(await page.locator('#login-error').textContent(), /bloqueio terminou/);
      await page.locator('#login-button').click();
      await page.locator('#login-error').filter({ hasText: 'E-mail ou senha incorretos.' }).waitFor();

      await page.locator('#open-password-reset').click();
      await page.locator('#password-reset-modal').waitFor({ state: 'visible' });
      await page.locator('#submit-password-reset').click();
      await page.locator('#password-reset-error').filter({ hasText: 'não está configurado' }).waitFor();
      assert.equal(await page.locator('#password-reset-fields').isHidden(), true);
      mailReady = true;
      await page.locator('#submit-password-reset').click();
      await page.locator('#password-reset-fields').waitFor({ state: 'visible' });
      assert.doesNotMatch(await page.locator('#password-reset-hint').textContent(), /Modo de desenvolvimento/);
      await page.locator('#password-reset-code').fill('111111');
      await page.locator('#password-reset-new').fill('New-fictitious-password-456!');
      await page.locator('#password-reset-confirmation').fill('Different-password-456!');
      await page.locator('#submit-password-reset').click();
      assert.equal(confirmationRequests, 0);
      assert.match(await page.locator('#password-reset-error').textContent(), /não são iguais/);
      await page.locator('#password-reset-confirmation').fill('New-fictitious-password-456!');
      await page.locator('#submit-password-reset').click();
      await page.locator('#password-reset-error').filter({ hasText: 'inválido' }).waitFor();
      await page.locator('#password-reset-code').fill('222222');
      await page.locator('#submit-password-reset').click();
      await page.locator('#password-reset-modal').waitFor({ state: 'hidden' });
      assert.equal(confirmationRequests, 2);
      assert.equal(await page.locator('#password').inputValue(), '');
      assert.match(await page.locator('#toast').textContent(), /Senha redefinida/);
      assert.deepEqual(errors, []);
    } finally { await browser.close(); }
  });
}
