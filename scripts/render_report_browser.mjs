import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, all) => {
  if (v.startsWith('--')) a.push([v.slice(2), all[i + 1]]);
  return a;
}, []));
for (const key of ['root', 'modules', 'browser']) if (!args[key]) throw new Error('Missing --' + key);
const root = path.resolve(args.root);
const require = createRequire(path.join(path.resolve(args.modules), '__p08_loader.cjs'));
const { chromium } = require('playwright');
const rendered = path.join(root, 'reports', 'rendered');
const qa = path.join(root, 'build', 'p08', 'qa');
await fs.mkdir(path.join(qa, 'slides'), { recursive: true });
const expectedIDs = [...Array.from({ length: 12 }, (_, i) => 's' + String(i + 1).padStart(2, '0')), ...Array.from({ length: 4 }, (_, i) => 'b' + String(i + 1).padStart(2, '0'))];
const result = {
  generated_at: new Date().toISOString(), viewport: { width: 1280, height: 720 },
  slide_count: 0, slide_ids: [], plot_count: 0, notes_count: 0,
  consoleErrors: [], blockedURLs: [], overflows: [], font_findings: [],
  screenshots: [], unresolved_tokens: [], pdf: {}, errors: []
};
const browser = await chromium.launch({ executablePath: args.browser, headless: true });
result.browser_version = browser.version();
result.expected_slide_ids = expectedIDs;
const context = await browser.newContext({ viewport: result.viewport, deviceScaleFactor: 1 });
await context.route(/^https?:\/\//, async route => {
  result.blockedURLs.push(route.request().url());
  await route.abort('blockedbyclient');
});
function observe(page, document) {
  page.on('pageerror', error => result.consoleErrors.push({ document, type: 'pageerror', message: error.message }));
  page.on('console', msg => { if (msg.type() === 'error') result.consoleErrors.push({ document, type: 'console', message: msg.text() }); });
}
async function settle(page) {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all([...document.images].map(im => im.complete ? Promise.resolve() : new Promise(resolve => {
      im.addEventListener('load', resolve, { once: true }); im.addEventListener('error', resolve, { once: true });
    })));
  });
}
try {
  const page = await context.newPage(); observe(page, 'slides');
  await page.goto(pathToFileURL(path.join(rendered, 'slides.html')).href, { waitUntil: 'load' });
  await page.waitForFunction(() => window.Reveal?.isReady?.(), { timeout: 30000 });
  await settle(page);
  await page.waitForFunction(() => [...document.querySelectorAll('.js-plotly-plot')].every(p => p._fullLayout && p.querySelector('.main-svg')), { timeout: 30000 });
  const inventory = await page.evaluate(() => {
    const slides = [...document.querySelectorAll('.reveal .slides section')].filter(s => !s.querySelector(':scope > section'));
    return { ids: slides.map((s, i) => s.id || 'slide-' + String(i + 1).padStart(2, '0')), notes: slides.filter(s => s.querySelector('aside.notes,.notes')).length,
      notes_text: slides.map(s => ({ id: s.id, text: s.querySelector('aside.notes,.notes')?.textContent.trim() || '' })),
      image_alt: [...document.querySelectorAll('.reveal img')].map(im => ({ src: im.getAttribute('src')?.slice(0, 120), alt: im.getAttribute('alt') })),
      plots: document.querySelectorAll('.js-plotly-plot').length,
      tokens: document.body.textContent.match(/\{\{(?:meta|v):[^{}]+\}\}/g) || [] };
  });
  result.slide_count = inventory.ids.length; result.slide_ids = inventory.ids; result.notes_count = inventory.notes;
  result.notes = inventory.notes_text; result.image_alt = inventory.image_alt;
  result.plot_count = inventory.plots; result.unresolved_tokens.push(...inventory.tokens);
  for (let i = 0; i < inventory.ids.length; i++) {
    await page.evaluate(index => {
      const slides = [...document.querySelectorAll('.reveal .slides section')].filter(s => !s.querySelector(':scope > section'));
      const target = slides[index]; const coordinates = Reveal.getIndices(target);
      Reveal.slide(coordinates.h, coordinates.v || 0, -1);
      target.querySelectorAll('.fragment').forEach(f => f.classList.add('visible'));
    }, i);
    await page.waitForTimeout(150);
    const findings = await page.evaluate(() => {
      const slide = Reveal.getCurrentSlide();
      const rect = slide.getBoundingClientRect();
      const footer = slide.querySelector('footer,.slide-footer,.source-footer,.sources,.slide-source');
      const bottom = footer ? footer.getBoundingClientRect().top : rect.bottom;
      const overflow = [], fonts = [];
      for (const el of slide.querySelectorAll('h1,h2,h3,p,li,td,th,table,figure,.js-plotly-plot,.chart-container')) {
        if (el.closest('aside.notes,.notes,footer,.slide-footer,.source-footer,.sources,.slide-source')) continue;
        const b = el.getBoundingClientRect(), style = getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || !b.width || !b.height) continue;
        if (b.left < rect.left - 3 || b.right > rect.right + 3 || b.top < rect.top - 3 || b.bottom > bottom + 3)
          overflow.push({ tag: el.tagName, text: el.textContent.trim().slice(0, 100), bounds: { x: b.x, y: b.y, width: b.width, height: b.height }, available_bottom: bottom });
        const size = parseFloat(style.fontSize);
        if (!el.matches('h1,h2,h3,p,li,td,th')) continue;
        const target = /^H[1-3]$/.test(el.tagName) ? 40 : 24;
        if (size < target - 0.5) fonts.push({ tag: el.tagName, text: el.textContent.trim().slice(0, 80), css_font_px: size, recommended_px: target });
      }
      const axes = [...slide.querySelectorAll('.xtick text,.ytick text,.g-xtitle text,.g-ytitle text,.legendtext,.annotation-text')].map(el => ({ text: el.textContent, css_font_px: parseFloat(getComputedStyle(el).fontSize) })).filter(x => x.css_font_px < 19.5);
      return { overflow, fonts, axes };
    });
    const id = inventory.ids[i];
    result.overflows.push(...findings.overflow.map(x => ({ slide: id, ...x })));
    result.font_findings.push(...findings.fonts.map(x => ({ slide: id, ...x })), ...findings.axes.map(x => ({ slide: id, role: 'plot_axis', recommended_px: 20, ...x })));
    const output = path.join(qa, 'slides', id.replace(/[^a-zA-Z0-9_-]/g, '_') + '.png');
    await page.screenshot({ path: output }); result.screenshots.push(path.relative(root, output));
  }
  const print = await context.newPage(); observe(print, 'slides_print');
  await print.goto(pathToFileURL(path.join(rendered, 'slides.html')).href + '?print-pdf', { waitUntil: 'load' });
  await print.waitForFunction(() => window.Reveal?.isReady?.());
  await settle(print);
  await print.waitForFunction(() => document.querySelectorAll('.pdf-page').length > 0, { timeout: 30000 });
  // Reveal print CSS turns percentage section height into the full paper height,
  // then offsets it by the slide margin. Keep the authored 1280x720 canvas.
  await print.addStyleTag({ content: '.reveal .slides section { height:720px !important; width:1280px !important; box-sizing:border-box !important; padding:10px 14px 105px !important; }' });
  await print.emulateMedia({ media: 'print' });
  result.pdf.layout = await print.evaluate(() => [...document.querySelectorAll('.pdf-page')].map(wrapper => {
    const slide = wrapper.querySelector('section');
    if (!slide) return { error: 'Print page has no slide' };
    const page = wrapper.getBoundingClientRect(), bounds = slide.getBoundingClientRect();
    const footer = slide.querySelector('.slide-source');
    const takeaway = slide.querySelector('.takeaway');
    const fit = el => {
      if (!el) return { missing: true, fits: false };
      const r = el.getBoundingClientRect();
      return { x:r.x-page.x, y:r.y-page.y, width:r.width, height:r.height, fits:r.left >= page.left && r.right <= page.right + 1 && r.top >= page.top && r.bottom <= page.bottom + 1 };
    };
    const textIssues = [...slide.querySelectorAll('h1,h2,h3,p,li,td,th,.xtick text,.ytick text,.legendtext,.annotation-text')].filter(el => !el.closest('.notes')).flatMap(el => {
      const style = getComputedStyle(el), r = el.getBoundingClientRect();
      const role = el.closest('.slide-source') ? 'source' : el.matches('h1,h2,h3') ? 'title' : el.closest('svg') ? 'axis' : 'body';
      const minimum = { source:20,title:40,axis:20,body:24 }[role];
      return (parseFloat(style.fontSize) < minimum - 0.5 || (r.width > 0 && r.bottom > page.bottom + 1)) ? [{ role,text:el.textContent.trim().slice(0,80),font_px:parseFloat(style.fontSize),minimum_px:minimum,outside_page:r.bottom > page.bottom+1 }] : [];
    });
    return { id:slide.id, section_width:bounds.width, section_height:bounds.height, footer:fit(footer), takeaway:fit(takeaway), text_issues:textIssues };
  }));
  if (result.pdf.layout.some(s => !s.footer?.fits || !s.takeaway?.fits || s.section_width !== 1280 || s.section_height !== 720 || s.text_issues?.length)) result.errors.push('Print slide footer/takeaway/font/text bounds validation failed');
  result.pdf.print_page_count = await print.locator('.pdf-page').count();
  result.pdf.notes_page_count = await print.locator('.speaker-notes-pdf').count();
  await print.pdf({ path: path.join(rendered, 'slides.pdf'), printBackground: true, preferCSSPageSize: true });
  const report = await context.newPage(); observe(report, 'report');
  await report.goto(pathToFileURL(path.join(rendered, 'report.html')).href, { waitUntil: 'load' }); await settle(report);
  result.unresolved_tokens.push(...await report.evaluate(() => document.body.textContent.match(/\{\{(?:meta|v):[^{}]+\}\}/g) || []));
  await report.screenshot({ path: path.join(qa, 'report.png'), fullPage: true });
  result.report_screenshot = path.relative(root, path.join(qa, 'report.png'));
  result.pdf.slides_exists = (await fs.stat(path.join(rendered, 'slides.pdf'))).size > 0;
  result.pdf.report_exists = await fs.stat(path.join(rendered, 'report.pdf')).then(s => s.size > 0, () => false);
  if (JSON.stringify(result.slide_ids) !== JSON.stringify(expectedIDs)) result.errors.push('Slide IDs/order differ from s01–s12,b01–b04');
  if (result.slide_count !== 16) result.errors.push('Expected 16 slides');
  if (result.notes.some(n => !n.text)) result.errors.push('Empty speaker notes');
  if (result.notes_count !== 16) result.errors.push('Expected notes on all 16 slides');
  if (result.pdf.print_page_count !== 16 || result.pdf.notes_page_count) result.errors.push('Expected exactly 16 print pages with no notes pages');
  if (result.unresolved_tokens.length) result.errors.push('Unresolved template tokens');
  if (result.consoleErrors.length) result.errors.push('Browser console errors');
} catch (error) { result.errors.push(error.stack || String(error)); }
finally {
  await browser.close();
  result.blockedURLs = [...new Set(result.blockedURLs)];
  result.passed = result.errors.length === 0;
  await fs.writeFile(path.join(root, 'build', 'p08', 'browser_validation.json'), JSON.stringify(result, null, 2) + '\n');
}
console.log(JSON.stringify({ passed: result.passed, slide_count: result.slide_count, plot_count: result.plot_count, overflows: result.overflows.length, font_findings: result.font_findings.length, errors: result.errors }));
if (!result.passed) process.exitCode = 1;
