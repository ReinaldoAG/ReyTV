/* Pruebas visuales y funcionales básicas. Ejecutar con node tests/smoke.cjs. */
const { chromium } = require('playwright');
const path = require('node:path');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const html = fs.readFileSync(path.resolve(__dirname, '../index.html'), 'utf8');
  const script = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
  assert.ok(script, 'Debe existir el script de Franche TV');
  new Function(script);
  for (const name of ['netflix', 'youtube', 'prime', 'disney', 'twitch']) {
    assert.ok(html.includes(`id:'${name}'`), `Debe estar incluido ${name}`);
  }
  console.log('Pruebas estáticas pasaron (HTML y sintaxis JS).');

  let browser;
  try {
    browser = await chromium.launch({ headless: true, executablePath: '/usr/bin/chromium', args: ['--no-sandbox'] });
  } catch (error) {
    if (/Operation not permitted|ENOENT|no usable sandbox|socket\(\) failed/i.test(String(error))) {
      console.warn('Navegador no disponible en este entorno: se omiten las pruebas visuales.');
      return;
    }
    throw error;
  }
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
  try {
    const address = `file://${path.resolve(__dirname, '../index.html')}`;
    await page.goto(address);
    assert.equal(await page.title(), 'Franche TV — Tu pantalla, tus reglas');
    assert.equal(await page.locator('.app-card').count(), 4);
    await page.keyboard.press('ArrowDown');
    assert.notEqual(await page.evaluate(() => document.activeElement?.tagName), 'BODY');
    await page.keyboard.press('/');
    assert.equal(await page.locator('#search').evaluate(el => document.activeElement === el), true);
    await page.locator('#search').fill('prime');
    assert.equal(await page.locator('.app-card').count(), 1);
    await page.locator('#search').fill('');
    await page.getByRole('button', { name: 'Añadir servicio' }).click();
    await page.locator('#custom-name').fill('Mi Cine');
    await page.locator('#custom-url').fill('https://example.com/');
    await page.getByRole('button', { name: 'Guardar acceso' }).click();
    assert.equal(await page.locator('.app-card').count(), 9);
    await page.reload();
    await page.getByRole('button', { name: 'Aplicaciones' }).click();
    assert.equal(await page.locator('.app-card').count(), 9);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#hero').isVisible(), true);
    await page.screenshot({ path: path.resolve(__dirname, '../../franche-tv-screenshot.png'), fullPage: true });
    console.log('Todas las pruebas funcionales pasaron.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
