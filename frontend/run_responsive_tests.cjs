const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const http = require('http');

const ROOT_DIR = path.resolve(__dirname, '..');
const SCREENSHOTS_DIR = path.join(ROOT_DIR, 'tests', 'screenshots');

if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

const VIEWPORTS = [
  { name: 'small-mobile', width: 320, height: 568 },
  { name: 'common-mobile', width: 360, height: 800 },
  { name: 'large-mobile-1', width: 390, height: 844 },
  { name: 'large-mobile-2', width: 430, height: 932 },
  { name: 'tablet-portrait', width: 768, height: 1024 },
  { name: 'tablet-landscape', width: 1024, height: 768 },
  { name: 'laptop', width: 1280, height: 720 },
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'large-desktop', width: 1920, height: 1080 },
];

function isServerHealthy(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.end();
  });
}

(async () => {
  console.log('====================================================');
  console.log('वाणीसंशोधक Playwright Responsive & A11y Test Runner');
  console.log('====================================================');

  const healthy = await isServerHealthy('http://127.0.0.1:8000/api/health');
  if (!healthy) {
    console.error('Server is not running on http://127.0.0.1:8000. Please start python run_server.py first.');
    process.exit(1);
  }
  console.log('✓ Target server is running and healthy at http://127.0.0.1:8000\n');

  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const results = [];

  for (const vp of VIEWPORTS) {
    console.log(`Testing Viewport: ${vp.name} (${vp.width}x${vp.height})...`);
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      userAgent: vp.width < 768 
        ? 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148' 
        : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    });

    const page = await context.newPage();
    const consoleErrors = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto('http://127.0.0.1:8000', { waitUntil: 'domcontentloaded' });

    // Allow React to hydrate and fetch data
    await page.waitForTimeout(1500);

    // 1. Check Horizontal Overflow
    const overflowInfo = await page.evaluate(() => {
      const scrollW = document.documentElement.scrollWidth;
      const innerW = window.innerWidth;
      return {
        hasOverflow: scrollW > innerW,
        scrollWidth: scrollW,
        innerWidth: innerW,
      };
    });

    // Capture Default View Screenshot
    const defaultShotPath = path.join(SCREENSHOTS_DIR, `${vp.name}_${vp.width}x${vp.height}_default.png`);
    await page.screenshot({ path: defaultShotPath, fullPage: true });

    // 2. Test Language Toggle Switch
    let langToggled = false;
    try {
      const enBtn = page.locator('button:visible:has-text("English"), button:visible:has-text("En")').first();
      if (await enBtn.isVisible()) {
        await enBtn.click();
        await page.waitForTimeout(250);

        const hiBtn = page.locator('button:visible:has-text("हिंदी"), button:visible:has-text("हिं")').first();
        if (await hiBtn.isVisible()) {
          await hiBtn.click();
          await page.waitForTimeout(250);
          langToggled = true;
        }
      }
    } catch (e) {
      console.warn(`  Language toggle warning on ${vp.name}:`, e.message);
    }

    // 3. Test Workspace Mode Switcher (Scan, Text, Split)
    let workspaceToggled = false;
    try {
      const scanBtn = page.locator('button:visible:has-text("पाण्डुलिपि")').first();
      const editorBtn = page.locator('button:visible:has-text("देवनागरी पाठ")').first();
      const splitBtn = page.locator('button:visible:has-text("तुलना")').first();

      if (await scanBtn.isVisible()) {
        await scanBtn.click();
        await page.waitForTimeout(200);
      }
      if (await editorBtn.isVisible()) {
        await editorBtn.click();
        await page.waitForTimeout(200);
      }
      if (await splitBtn.isVisible()) {
        await splitBtn.click();
        await page.waitForTimeout(200);
        workspaceToggled = true;
      }
    } catch (e) {
      console.warn(`  Workspace toggle warning on ${vp.name}:`, e.message);
    }

    // 4. Test Word Inspector Modal & Escape key
    let modalTested = false;
    try {
      // Switch to Text Editor view so word chips are visible and scrollable
      const editorTab = page.locator('button:visible:has-text("देवनागरी पाठ")').first();
      if (await editorTab.isVisible()) {
        await editorTab.click();
        await page.waitForTimeout(300);
      }

      // Click the first word token button inside text editor
      const wordToken = page.locator('button[aria-label*="विश्वास"]').first();
      if (await wordToken.isVisible()) {
        await wordToken.scrollIntoViewIfNeeded();
        await wordToken.click();
        await page.waitForTimeout(400);

        const modal = page.locator('div[role="dialog"]');
        if (await modal.isVisible()) {
          // Capture modal view screenshot
          const modalShotPath = path.join(SCREENSHOTS_DIR, `${vp.name}_${vp.width}x${vp.height}_modal.png`);
          await page.screenshot({ path: modalShotPath, fullPage: true });

          // Test Escape key closes modal
          await page.keyboard.press('Escape');
          await page.waitForTimeout(300);
          const modalStillOpen = await modal.isVisible().catch(() => false);
          modalTested = !modalStillOpen;
        }
      }

      // Restore to split view if available
      const splitTab = page.locator('button:visible:has-text("तुलना")').first();
      if (await splitTab.isVisible()) {
        await splitTab.click();
        await page.waitForTimeout(200);
      }
    } catch (e) {
      console.warn(`  Modal test warning on ${vp.name}:`, e.message);
    }

    // 5. Test Image Adjustment & Crop Studio Modal
    let cropStudioTested = false;
    try {
      const adjustBtn = page.locator('button:visible:has-text("काटें व घुमाएँ"), button:visible:has-text("Crop & Rotate")').first();
      if (await adjustBtn.isVisible()) {
        await adjustBtn.click();
        await page.waitForTimeout(500);

        const cropModal = page.locator('div[role="dialog"][aria-labelledby="adjustment-studio-title"]');
        if (await cropModal.isVisible()) {
          // Capture crop studio view screenshot
          const cropShotPath = path.join(SCREENSHOTS_DIR, `${vp.name}_${vp.width}x${vp.height}_crop_studio.png`);
          await page.screenshot({ path: cropShotPath, fullPage: true });

          // Test escape key closes adjustment studio
          await page.keyboard.press('Escape');
          await page.waitForTimeout(300);
          const stillOpen = await cropModal.isVisible().catch(() => false);
          cropStudioTested = !stillOpen;
        }
      }
    } catch (e) {
      console.warn(`  Crop studio test warning on ${vp.name}:`, e.message);
    }

    const testPassed = !overflowInfo.hasOverflow && consoleErrors.length === 0;

    results.push({
      viewport: `${vp.name} (${vp.width}x${vp.height})`,
      width: vp.width,
      height: vp.height,
      horizontalOverflow: overflowInfo.hasOverflow,
      scrollWidth: overflowInfo.scrollWidth,
      innerWidth: overflowInfo.innerWidth,
      langToggled,
      workspaceToggled,
      modalTested,
      cropStudioTested,
      consoleErrorsCount: consoleErrors.length,
      screenshot: path.relative(ROOT_DIR, defaultShotPath),
      status: testPassed ? 'PASS' : 'FAIL',
    });

    console.log(`  ✓ Finished ${vp.name}: Overflow=${overflowInfo.hasOverflow ? 'YES (FAIL)' : 'NO (PASS)'}, EscapeKeyModal=${modalTested ? 'PASS' : 'WARN'}, CropStudio=${cropStudioTested ? 'PASS' : 'WARN'}, Errors=${consoleErrors.length}`);
    await context.close();
  }

  await browser.close();

  console.log('\n====================================================');
  console.log('Automated Viewport Coverage Summary:');
  console.log('====================================================');
  console.table(results.map(r => ({
    Viewport: r.viewport,
    Overflow: r.horizontalOverflow ? `FAIL (${r.scrollWidth}px)` : 'PASS',
    LangSwitch: r.langToggled ? 'PASS' : 'WARN',
    WorkspaceMode: r.workspaceToggled ? 'PASS' : 'N/A',
    ModalEscape: r.modalTested ? 'PASS' : 'WARN',
    Errors: r.consoleErrorsCount,
    Status: r.status,
  })));

  // Write detailed results to JSON
  fs.writeFileSync(path.join(ROOT_DIR, 'tests', 'responsive_test_results.json'), JSON.stringify(results, null, 2));
  console.log(`\nDetailed test log saved to tests/responsive_test_results.json`);
  console.log(`Captured all screenshots in: ${SCREENSHOTS_DIR}`);
})();
