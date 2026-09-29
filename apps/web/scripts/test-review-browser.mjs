import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
const browser = await chromium.launch({ channel: "chrome", headless: true });
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(process.env.REVIEW_TEST_URL || "http://127.0.0.1:3101");
  await page.screenshot({
    path: "/private/tmp/rasputin-login-desktop.png",
    fullPage: false,
  });
  await page.evaluate(() =>
    localStorage.setItem(
      "sb-laodipuodgrpqykrupms-auth-token",
      JSON.stringify({
        access_token: "synthetic",
        refresh_token: "synthetic",
        expires_at: Math.floor(Date.now() / 1000) + 3600,
        token_type: "bearer",
        user: {
          id: "synthetic",
          email: "test@example.invalid",
          aud: "authenticated",
          role: "authenticated",
          app_metadata: {},
          user_metadata: {},
        },
      }),
    ),
  );
  const rows = [
    {
      document: "1",
      issued: "2026-08-01",
      code: "P1",
      description: "Refeição sintética",
      ncm: "21069090",
      cfop: "5102",
      nature: "Venda",
      category: "Alimento",
      icms_rate: "4.0",
      icms_cst: "00",
      pis_cst: "01",
      cofins_cst: "01",
      value: "100",
      icms_value: "4",
      source: { line: 7 },
    },
    {
      document: "2",
      issued: "2026-08-01",
      code: "P2",
      description: "Bebida sintética",
      ncm: "22042100",
      cfop: "5102",
      nature: "Venda",
      category: "Bebida",
      icms_rate: "25.0",
      icms_cst: "00",
      pis_cst: "01",
      cofins_cst: "01",
      value: "200",
      icms_value: "50",
      source: { line: 8 },
    },
    {
      document: "3",
      issued: "2026-08-01",
      code: "P3",
      description: "Devolução sintética",
      ncm: "21069090",
      cfop: "5202",
      nature: "Devolução de compra para comercialização",
      category: "Alimento",
      icms_rate: "18.0",
      icms_cst: "20",
      pis_cst: "49",
      cofins_cst: "49",
      value: "100",
      icms_value: "18",
      source: { line: 9 },
    },
  ];
  const analysis = {
    id: "a1",
    status: "concluida",
    parcial: true,
    periodo_ini: "2026-08-01",
    periodo_fim: "2026-08-31",
    resumo: { findings: 0 },
    result_payload: {
      summary: {
        review_rows: rows,
        base_review: {
          missing_icms: 1,
          other_difference: 0,
          compatible: 1,
          unassessed: 0,
          rows: [
            {
              document: "2",
              issued: "2026-08-01",
              source: { line: 8 },
              description: "Bebida sintética",
              cfop: "5102",
              kind: "missing_icms",
              operation_value: "200",
              icms: "50",
              expected_base: "150",
              pis_base: "200",
              cofins_base: "200",
              pis_cst: "01",
              cofins_cst: "01",
            },
          ],
        },
      },
      findings: [
        {
          id: "guess",
          code: "D05",
          message: "SUSPEITA INDEVIDA",
          product: "P1",
          evidence: [],
          expected: {},
        },
      ],
      skipped: [],
      input_hash: "synthetic",
      rules_hash: "synthetic",
    },
  };
  analysis.resumo = {
    findings: 1,
    base_review: analysis.result_payload.summary.base_review,
  };
  let reissued = false;
  await page.route("https://download.example.invalid/report.pdf", (route) =>
    route.fulfill({
      contentType: "application/pdf",
      headers: { "Access-Control-Allow-Origin": "*" },
      body: "%PDF-1.7\n%%EOF",
    }),
  );
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/analyses/a1/reissue") reissued = true;
    const data =
      path === "/api/analyses/a1/download/pdf"
        ? { url: "https://download.example.invalid/report.pdf" }
        : path === "/api/me"
          ? {
              user_id: "synthetic",
              role: "admin",
              organization: {
                id: "org1",
                nome: "Escritório sintético",
                branding: {},
              },
            }
          : path === "/api/clients"
            ? [
                {
                  id: "c1",
                  razao_social: "Cliente sintético",
                  cnpj: "11111111000111",
                  profiles: [],
                },
              ]
            : path === "/api/analyses"
              ? [analysis]
              : path === "/api/analyses/a1"
                ? analysis
                : [];
    await route.fulfill({
      status: 200,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "*",
      },
      contentType: "application/json",
      body: JSON.stringify(data),
    });
  });
  await page.reload();
  await page
    .getByRole("button", { name: "Abrir última conferência" })
    .waitFor();
  await page.locator(".mascot-stage img").evaluate((img) => img.decode());
  await page.screenshot({
    path: "/private/tmp/rasputin-dashboard-desktop.png",
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "/private/tmp/rasputin-dashboard-mobile.png",
    fullPage: false,
  });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    ),
    false,
  );
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page
    .getByRole("button", { name: "Ver resultado", exact: true })
    .click();
  await page.getByText(/linha[s]? sem descontar o ICMS da base/).waitFor();
  await page.screenshot({
    path: "/private/tmp/rasputin-report-desktop.png",
    fullPage: false,
  });
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar PDF para cliente" }).click();
  const file = await downloaded;
  assert.equal(file.suggestedFilename(), "Rasputin-conferencia-2026-08-01.pdf");
  assert.equal(reissued, false);
  await page.getByRole("status").filter({ hasText: "PDF exportado" }).waitFor();
  assert.equal(await page.getByText("SUSPEITA INDEVIDA").count(), 0);
  assert.equal(
    await page.getByRole("button", { name: /Não avaliadas/ }).count(),
    0,
  );
  await page.getByText("Ver 1 linha com divergência na base").click();
  await page
    .getByRole("cell", { name: "ICMS não descontado", exact: true })
    .waitFor();
  await page.getByText("Ver 1 linha com divergência na base").click();
  await page.getByRole("button", { name: /Itens por CFOP/ }).click();
  assert.equal(
    await page.getByRole("dialog").locator("tbody tr:visible").count(),
    3,
  );
  await page.getByLabel("CFOP", { exact: true }).selectOption("5202");
  assert.equal(
    await page.getByRole("dialog").locator("tbody tr:visible").count(),
    1,
  );
  await page
    .getByRole("cell", { name: /Devolução de compra para comercialização/ })
    .waitFor();
  await page.getByLabel("CFOP", { exact: true }).selectOption("");
  await page.getByLabel("Alíquota ICMS", { exact: true }).selectOption("25.0");
  await page.getByRole("cell", { name: /Bebida sintética/ }).waitFor();
  assert.equal(
    await page.getByRole("dialog").locator("tbody tr:visible").count(),
    1,
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".modal-body").evaluate((el) => {
    el.parentElement.scrollTop = 0;
  });
  await page.screenshot({
    path: "/private/tmp/rasputin-review-mobile.png",
    fullPage: false,
  });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    ),
    false,
  );
  await page.keyboard.press("Escape");
  assert.equal(await page.getByRole("dialog").count(), 0);
  await page.getByRole("button", { name: "Clientes", exact: true }).click();
  await page
    .getByRole("button", { name: "Cadastrar cliente", exact: true })
    .click();
  await page.getByRole("dialog").waitFor();
  await page.keyboard.press("Shift+Tab");
  assert.equal(
    await page.evaluate(
      () => !!document.activeElement?.closest('[role="dialog"]'),
    ),
    true,
  );
  await page.screenshot({
    path: "/private/tmp/rasputin-client-form-mobile.png",
    fullPage: false,
  });
  await page.keyboard.press("Escape");
  assert.deepEqual(errors, []);
  console.log(
    "PASS: novo painel, mascote, gráfico, relatório, exportação PDF, filtros, modal acessível e mobile.",
  );
} finally {
  await browser.close();
}
