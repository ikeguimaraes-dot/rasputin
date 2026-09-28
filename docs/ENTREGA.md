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
2. Publicação de frontend/worker. A prévia local da interface
   não constitui ambiente de produção operacional.

## Limites intencionais

Ver [contrato fiscal](fiscal/contrato.md). O produto confere documentos: não apura automaticamente
DAS, IRPJ, CSLL, créditos ou valores recolhidos. Fases 2–4, SPED, coletores, APIs fiscais e
atualização legal automática continuam fora do MVP. A aprovação de uma regra é uma ação do
responsável do escritório, não uma decisão da IA.

O teste usa Auth/Storage simulados quando valida o pipeline com PostgreSQL temporário; os testes
remotos de Auth/Storage confirmaram acesso e buckets, sem usar arquivos fiscais reais.
O fluxo completo com usuário autenticado e relatório no Storage remoto ainda não foi validado.
