# Entrega — 28/09/2026

Sistema de auditoria documental e apuração assistida para restaurantes em Simples Nacional,
Lucro Presumido e Lucro Real, em modo somente leitura.

## Funcionalidades

Login Supabase, organizações isoladas, clientes e perfis por vigência, importação XML/ZIP e
XLS/XLSX/CSV, confirmação de mapeamento, fila, análises documentais, regras particulares
com aprovação, histórico e relatórios PDF/XLSX.

Catálogo oficial versionado de 2026: 14 referências, parâmetros federais/ICMS SP e 10.515
códigos NCM completos. Os extratos consultados e a tabela NCM original estão arquivados;
os registros informam exatamente qual conteúdo foi capturado e seu hash.

Sete módulos de apuração: Simples Anexo I, Presumido trimestral, Real trimestral,
Real anual acumulado, PIS/COFINS mensal, ICMS especial SP e saldo de ICMS próprio escriturado.
Dados contábeis e enquadramentos são declarados. Apurações salvas são imutáveis, com entradas,
perfil, catálogo e resultados preservados; download privado por URL assinada.

## Verificação

- 95 testes automatizados passaram; cobertura total 86%, motor de apuração 95%.
- Pipeline de documentos e apurações, exportação PDF/XLSX, idempotência e isolamento por organização.
- Seis migrations, RLS, revogação de escrita direta e imutabilidade verificadas em PostgreSQL isolado.
- Lint e TypeScript aprovados. Build e implantação são conferidos a cada publicação pelo CI.
- Testes usam dados sintéticos, sem documentos reais dos clientes.

## Produção

- Interface: https://rasputin-auditoria.vercel.app
- API/worker: https://auditoria-api-production-f923.up.railway.app
- Repositório: https://github.com/ikeguimaraes-dot/rasputin, branch main.
- Vercel: apps/web. Railway: worker/Dockerfile. Supabase: Auth, PostgreSQL e buckets privados.
- Credenciais privilegiadas permanecem fora do Git e do navegador.

## Escopo fiscal

Ver [contrato fiscal](fiscal/contrato.md) para condições exatas e cobertura. O sistema não
classifica automaticamente todos os produtos nem substitui a escrituração. Não calcula
ST/FCP/DIFAL por produto nas 27 UFs, outros anexos do Simples ou IBS/CBS. Não transmite guias.
O ajuste anual do Presumido é informado pelo usuário após conferência dos trimestres anteriores.
Falta de dados necessários impede salvar apuração, sem transformar ausência em imposto zero.
