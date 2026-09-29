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
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const data =
      path === "/api/me"
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
    .getByRole("button", { name: "Ver resultado", exact: true })
    .click();
  await page.getByText(/linhas sem descontar o ICMS da base/).waitFor();
  assert.equal(await page.getByText("SUSPEITA INDEVIDA").count(), 0);
  assert.equal(
    await page.getByRole("button", { name: /Não avaliadas/ }).count(),
    0,
  );
  await page.getByText("Ver as 1 linhas com divergência na base").click();
  await page
    .getByRole("cell", { name: "ICMS não descontado", exact: true })
    .waitFor();
  await page.getByText("Ver as 1 linhas com divergência na base").click();
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
  await page.screenshot({
    path: "/private/tmp/rasputin-review-mobile.png",
    fullPage: true,
  });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    ),
    false,
  );
  assert.deepEqual(errors, []);
  console.log(
    "PASS: CFOP, natureza, alíquota, itens sem apontamento e layout mobile.",
  );
} finally {
  await browser.close();
}
