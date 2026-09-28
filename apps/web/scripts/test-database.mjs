// PostgreSQL WASM isolado. Nenhum acesso ao Supabase real.
import { PGlite } from "@electric-sql/pglite";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
const root = resolve(import.meta.dirname, "../../..");
const db = await PGlite.create();
await db.exec(readFileSync(resolve(root, "supabase/tests/bootstrap.sql"), "utf8"));
try {
  for (const file of readdirSync(resolve(root, "supabase/migrations"))
    .filter((f) => f.endsWith(".sql"))
    .sort()) {
    await db.exec(
      readFileSync(resolve(root, "supabase/migrations", file), "utf8"),
    );
    console.log("Migration OK:", file);
  }
  await db.exec(
    readFileSync(resolve(root, "supabase/tests/rls_isolation.sql"), "utf8"),
  );
  console.log("RLS original OK");
  await db.exec(
    readFileSync(resolve(root, "supabase/tests/runtime_integrity.sql"), "utf8"),
  );
  console.log("Integridade, imutabilidade e isolamento Storage OK");
  if (process.argv.includes("--serve")) {
    const { PGLiteSocketServer } = await import("@electric-sql/pglite-socket");
    const port = Number(process.env.TEST_DB_PORT || 55432);
    const server = new PGLiteSocketServer({ db, host: "127.0.0.1", port });
    await server.start();
    console.log(
      `TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:${port}/postgres`,
    );
    process.on("SIGINT", async () => {
      await server.stop();
      await db.close();
      process.exit(0);
    });
  } else await db.close();
} catch (e) {
  console.error("SQL validation failed:", e.message);
  await db.close();
  process.exit(1);
}
