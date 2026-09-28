# Entrega — 28/09/2026

## Implementado

MVP de conferência fiscal: interface, login Supabase, escritório, clientes com três regimes,
perfis por vigência, XML/ZIP e planilhas, mapeamento confirmado, BIFF8 conservador, fila,
checagens determinísticas, propostas/aprovação de regras, snapshots imutáveis, PDF/XLSX,
logo/cores/rodapé e auditoria. Documentação e configurações de deploy incluídas.

## Verificado

- 65 testes passaram; cobertura de código total 84%, motor 95%.
- Pipeline integrado: API → fila → XML/planilha → análise → PDF/XLSX → reemissão.
- Testes de regras propostas, vigência, todos os regimes, ausência de dados e falso positivo B2B.
- PostgreSQL isolado: migrations, RLS, Storage, coerência entre cliente/upload e imutabilidade.
- Autenticação valida usuário remoto e associação à organização; URLs de download são assinadas.
- Retentativa após falha de Storage e continuidade após arquivo inválido.
- Build Next.js e TypeScript; navegação desktop/mobile sem erro JavaScript ou overflow horizontal.
- `.env` e `.env.local` ignorados pelo Git; chave privilegiada não aparece no bundle do navegador.
- Supabase remoto: endpoints Auth/Storage responderam; buckets `uploads` e `reports` criados privados.
- Conexão Session pooler autenticada; quatro migrations aplicadas no banco remoto sem conflito
  com as tabelas preexistentes. Testes de RLS e integridade executados com rollback e aprovados.
- API local: `/health` e `/ready` responderam 200; `/api/me` sem login respondeu 401;
  CORS da prévia local verificado. Inicialização com reload corrigida para evitar execução duplicada.

## Dependências externas ainda pendentes

1. Planilha fiscal original e validação de conteúdo pelo responsável fiscal. Não existem regras
   tributárias de produção pré-aprovadas. O seed importado entra na área de revisão.

## Implantação

- Frontend: https://rasputin-auditoria.vercel.app (Vercel, projeto `rasputin-auditoria`).
- API/worker: https://auditoria-api-production-f923.up.railway.app (Railway,
  projeto `rasputin-auditoria-fiscal`, serviço `auditoria-api`).
- Ambos conectados ao GitHub `ikeguimaraes-dot/rasputin`, branch `main`.
- Vercel usa a raiz `apps/web`; Railway usa `worker/Dockerfile` com contexto na raiz.
- Segredos do banco e Storage configurados somente no Railway; frontend recebe URL e chave pública.
- Endpoints públicos `/ready` e interface responderam 200; API sem autenticação respondeu 401.
- Navegação no navegador de produção com sessão real e dados sintéticos passou, sem erros JavaScript.
- CI do GitHub passou no commit `c4ac5f4`.
- Fluxo remoto completo aprovado nos três regimes: login, organização, cliente, upload CSV,
  fila, análise, PDF e XLSX baixados por URL assinada. Resultados corretamente parciais sem regras aprovadas.
- Quinta migration corrige a remoção de autor em Auth preservando análises concluídas;
  edição direta continua bloqueada. Teste de regressão passou localmente e no Supabase real.
- Conta temporária de validação removida com sucesso.

## Limites intencionais

Ver [contrato fiscal](fiscal/contrato.md). O produto confere documentos: não apura automaticamente
DAS, IRPJ, CSLL, créditos ou valores recolhidos. Fases 2–4, SPED, coletores, APIs fiscais e
atualização legal automática continuam fora do MVP. A aprovação de uma regra é uma ação do
responsável do escritório, não uma decisão da IA.

O teste usa Auth/Storage simulados quando valida o pipeline com PostgreSQL temporário; os testes
remotos de Auth/Storage confirmaram acesso e buckets, sem usar arquivos fiscais reais.
Testes posteriores de implantação usam conta temporária e dados sintéticos no ambiente remoto.
O histórico fica em organização isolada `VALIDAÇÃO TÉCNICA — DADOS SINTÉTICOS`; a conta
temporária é removida após os testes. Esses testes verificam o fluxo, não validam legislação.
