const { chromium } = require("playwright-core");

(async () => {
  const browser = await chromium.launch({ headless: false, args: ["--start-maximized"] });
  const context = await browser.newContext({ viewport: null });
  const page = await context.newPage();

  await page.goto("http://localhost:3000/", { waitUntil: "networkidle" });
  await page.click('text="Request Demo"');

  console.log("WAITING_FOR_MANUAL_SIGNIN");
  await page.waitForURL(/\/claims\/new/, { timeout: 300000 });
  console.log("SIGNED_IN_LANDED_ON_CLAIMS_NEW:", page.url());

  await browser.close();
})().catch((err) => {
  console.error("SCRIPT_FAILED", err);
  process.exit(1);
});
