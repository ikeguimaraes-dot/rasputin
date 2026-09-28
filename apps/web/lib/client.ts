import { createClient } from "@supabase/supabase-js";
export function supabaseClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key)
    throw new Error(
      "Configure as variáveis públicas do Supabase em apps/web/.env.local.",
    );
  return createClient(url, key);
}
export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const regimes: Record<string, string> = {
  simples: "Simples Nacional",
  presumido: "Lucro Presumido",
  real: "Lucro Real",
};
export const formatDate = (v: string) =>
  new Date(v.slice(0, 10) + "T12:00:00").toLocaleDateString("pt-BR");
export const money = (v: string | number) =>
  Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
