export type Profile = {
  uf: string;
  regime_federal: string;
  valid_from: string;
  valid_to?: string | null;
  optante_regime_especial_rest: boolean;
  contribuinte_ipi: boolean;
  metodo_pis_cofins?: string | null;
};
export type Client = {
  id: string;
  razao_social: string;
  cnpj: string;
  profiles: Profile[];
};
export type Upload = {
  id: string;
  nome: string;
  tipo: string;
  status: string;
  parcial: boolean;
  ingestion_report?: {
    read?: number;
    discarded?: number;
    errors?: unknown[];
    warnings?: string[];
  };
};
export type Summary = {
  findings: number;
  severity: Record<string, number>;
  skipped: number;
  potential_impact: Record<string, string>;
  limitations: string[];
};
export type Finding = {
  id: string;
  code: string;
  severity: string;
  message: string;
  product: string;
  description: string;
  impact: string | null;
  source_url?: string;
  legal_basis: string;
  expected: Record<string, unknown>;
  evidence: {
    document: string;
    issued: string;
    item: {
      n_item: number;
      ncm: string;
      cfop: string;
      source: Record<string, unknown>;
    };
  }[];
};
export type Analysis = {
  id: string;
  status: string;
  periodo_ini: string;
  periodo_fim: string;
  parcial: boolean;
  resumo?: Summary;
  erro?: string;
  result_payload?: {
    findings: Finding[];
    skipped: { code: string; reason: string; source: unknown }[];
    rules_hash: string;
    input_hash: string;
  };
};
export type Rule = {
  id: string;
  code: string;
  status: string;
  definition: {
    title: string;
    regimes: string[];
    valid_from: string;
    source_url: string;
    legal_basis: string;
    expected: Record<string, unknown>;
    [key: string]: unknown;
  };
};
export type Me = {
  user_id: string;
  role: string;
  organization: {
    id: string;
    nome: string;
    branding: Record<string, string>;
  } | null;
};
export type Preview = {
  sheets: string[];
  sheet: string;
  headers: string[];
  signature: string;
  sample: string[][];
  rows: number;
  warnings: string[];
  partial: boolean;
  fields: Record<string, string>;
};
export type Call = <T = unknown>(
  path: string,
  body?: unknown,
  method?: string,
) => Promise<T>;
