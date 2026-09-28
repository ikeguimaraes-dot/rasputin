import { chromium } from "@playwright/test";
const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto("http://127.0.0.1:3100");
await page.getByRole("heading", { name: "Bem-vindo de volta" }).waitFor();
await page.screenshot({
  path: "/private/tmp/rasputin-login.png",
  fullPage: true,
});
const project = "laodipuodgrpqykrupms";
const fakeSession = {
  access_token: "synthetic-test-token",
  refresh_token: "synthetic-refresh",
  expires_in: 3600,
  expires_at: Math.floor(Date.now() / 1000) + 3600,
  token_type: "bearer",
  user: {
    id: "aaaaaaaa-1111-1111-1111-111111111111",
    email: "teste@example.invalid",
    aud: "authenticated",
    role: "authenticated",
    app_metadata: {},
    user_metadata: {},
    created_at: "2026-01-01T00:00:00Z",
  },
};
await page.evaluate(
  ({ project, fakeSession }) =>
    localStorage.setItem(
      `sb-${project}-auth-token`,
      JSON.stringify(fakeSession),
    ),
  { project, fakeSession },
);
const client = {
  id: "c1111111-1111-1111-1111-111111111111",
  razao_social: "Restaurante sintético",
  cnpj: "11111111000111",
  profiles: [
    {
      uf: "SP",
      regime_federal: "real",
      valid_from: "2026-01-01",
      optante_regime_especial_rest: false,
      contribuinte_ipi: false,
    },
  ],
};
await page.route("http://localhost:8000/api/**", async (route) => {
  const path = new URL(route.request().url()).pathname;
  const data =
    path === "/api/me"
      ? {
          user_id: fakeSession.user.id,
          role: "admin",
          organization: {
            id: "11111111-1111-1111-1111-111111111111",
            nome: "Escritório de teste",
            branding: {},
          },
        }
      : path === "/api/clients"
        ? [client]
        : [];
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(data),
    headers: { "Access-Control-Allow-Origin": "*" },
  });
});
await page.reload();
await page.getByRole("heading", { name: "Clareza em cada análise." }).waitFor();
await page.screenshot({
  path: "/private/tmp/rasputin-dashboard.png",
  fullPage: true,
});
await page
  .getByRole("button", { name: "Enviar documentos", exact: true })
  .click();
await page.getByRole("dialog").waitFor();
await page.getByRole("button", { name: "Fechar", exact: true }).click();
await page.getByRole("button", { name: "Clientes", exact: true }).click();
await page
  .getByRole("button", { name: "Cadastrar cliente", exact: true })
  .click();
await page.getByRole("dialog").waitFor();
const regimes = await page
  .locator('select[name="regime"] option')
  .allTextContents();
if (regimes.length !== 3) throw new Error("Regimes incompletos");
await page.getByRole("button", { name: "Fechar", exact: true }).click();
await page.getByRole("button", { name: "Base de regras", exact: true }).click();
await page
  .getByRole("heading", { name: "Base de regras", exact: true })
  .waitFor();
await page.setViewportSize({ width: 390, height: 844 });
await page.getByRole("button", { name: "Visão geral", exact: true }).click();
await page.screenshot({
  path: "/private/tmp/rasputin-mobile.png",
  fullPage: true,
});
const overflow = await page.evaluate(
  () => document.documentElement.scrollWidth > window.innerWidth,
);
if (overflow) throw new Error("Overflow horizontal no mobile");
if (errors.length) throw new Error(errors.join("\n"));
console.log(
  "Browser OK: login, dashboard, upload, clientes, três regimes, regras e mobile.",
);
await browser.close();
