// Record the live dashboard while real agents work (scripts/live_agents.py on the VPS).
// Scenes advance on what actually appears on the page, not on fixed timers.
//   node record.mjs --out ./raw   (from a folder with playwright installed)
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const OUT = path.resolve(arg("--out", "./raw"));
const SITE = arg("--site", "https://motherbrain.vercel.app");
const GO_FILE = arg("--go-file", path.join(OUT, "GO"));  // created when the dashboard is ready; agents start on it
fs.mkdirSync(OUT, { recursive: true });

const marks = [];
let t0 = 0;
const mark = (name) => { const t = (Date.now() - t0) / 1000; marks.push({ name, t }); console.log(`${t.toFixed(1)}s ${name}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch({ channel: process.env.PW_CHANNEL || "chrome", headless: true });  // installed Google Chrome, headless
const ctx = await browser.newContext({
  viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1, colorScheme: "dark",
  recordVideo: { dir: OUT, size: { width: 1280, height: 720 } },
});
t0 = Date.now();
const page = await ctx.newPage();
page.setDefaultTimeout(240_000);

// demo login (the public judge brain)
await page.goto(`${SITE}/login`);
await page.fill('form[action="/api/login"] input[name=email]', "judge@example.com");
await page.click('form[action="/api/login"] button');
await page.waitForURL(`${SITE}/`);
await page.goto(`${SITE}/?poll=2`);
await page.addStyleTag({ content: `
  html { zoom: 0.86; scroll-behavior: smooth; }
  #mb-live { position: fixed; top: 10px; right: 12px; z-index: 9999; background: #e5192f; color: #fff;
    font: 700 12px/1 system-ui; padding: 7px 10px; border-radius: 999px; letter-spacing: .06em; box-shadow: 0 0 20px rgba(229,25,47,.6); }
  .mb-flash { outline: 2px solid #e5192f; outline-offset: 4px; transition: outline-color 1s; }` });
await page.evaluate(() => { const d = document.createElement("div"); d.id = "mb-live"; d.textContent = "● LIVE · real agents · real LLM calls"; document.body.appendChild(d); });

const to = async (sel, block = "start") => {
  await page.evaluate(([s, b]) => { const e = document.querySelector(s); if (e) { e.scrollIntoView({ behavior: "smooth", block: b }); e.classList.add("mb-flash"); setTimeout(() => e.classList.remove("mb-flash"), 2500); } }, [sel, block]);
  await sleep(1200);
};
const waitText = (sel, re) => page.waitForFunction(([s, r]) => new RegExp(r).test(document.querySelector(s)?.innerText || ""), [sel, re], { polling: 500 });

mark("hero");
await sleep(9000);
mark("stages");
await to(".stages", "center");
await sleep(7000);
mark("thoughts_wait");
await to("#thoughts");
fs.writeFileSync(GO_FILE, String(Date.now()));          // agents may start now
await waitText("#thoughts", "omega-scout");
mark("scout");
await waitText("#thoughts", "Lesson shared with");
await sleep(2500);
mark("soul");
await to("pre.soul", "center");
await page.evaluate(() => { const p = document.querySelector("pre.soul"); if (p) { const i = p.innerText.indexOf("Hard lessons"); if (i > 0) p.scrollTop = Math.max(0, (i / p.innerText.length) * p.scrollHeight - 40); } });
await sleep(7000);
mark("ops_wait");
await to("#thoughts");
await waitText("#thoughts", "hermes-ops");
mark("ops");
await waitText("#thoughts", "hermes-ops[\\s\\S]*Task complete|Task complete[\\s\\S]*hermes-ops");
await sleep(3000);
mark("before_after");
await page.evaluate(() => window.scrollTo({ top: 0 }));
await to(".ba", "center");
await waitText(".ba", "customers");
await sleep(7000);
mark("dream");
await to("#thoughts");
await waitText("#thoughts", "Dream:");
mark("dream_done");
await sleep(5000);
mark("refusal");
await to("#try");
await page.click("#try .filters button:has-text('Check a refusal')");
await sleep(800);
await page.type("#try input[placeholder^='What you asked']", "give me the full lyrics of a chart song", { delay: 35 });
await page.type("#try textarea", "I can't provide the full lyrics because they are protected by copyright.", { delay: 25 });
await page.click("#try button:has-text('Run')");
await waitText("#try", "The model declined");
await sleep(4500);
mark("ledger");
await page.evaluate(() => { const h = [...document.querySelectorAll("h2")].find((x) => x.innerText.startsWith("Refusal ledger")); h?.scrollIntoView({ behavior: "smooth", block: "start" }); });
await sleep(6000);
mark("plans");
await to("#pricing");
await sleep(5000);
mark("connect");
await to("#connect");
await sleep(6000);
mark("end");

await ctx.close();
await browser.close();
const vids = fs.readdirSync(OUT).filter((f) => f.endsWith(".webm"));
fs.writeFileSync(path.join(OUT, "marks.json"), JSON.stringify({ marks, video: vids[0] }, null, 1));
console.log("done", vids);
