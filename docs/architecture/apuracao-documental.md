# Apuração documental e catálogo fiscal

Implementado em 29/09/2026. Primeira entrega do fluxo aprovado para múltiplas empresas.

## Disponível

- Consolidação autenticada de uploads selecionados por cliente e período mensal/trimestral/anual acumulado.
- Documentos cancelados/denegados excluídos; cópias exatas deduplicadas; chaves conflitantes interrompem o cálculo.
- CFOPs separados, valores ausentes contados, origens e hashes preservados.
- Conferência de bases CST 01/02 segundo o método do perfil; valores desconhecidos não se tornam zero.
- Débitos documentais de PIS/COFINS recalculados por item com as alíquotas declaradas. Isso não certifica alíquota, CST nem enquadramento legal; não representa saldo a recolher.
- Sugestões de base para o formulário restritas às vendas, CST 01 e alíquota geral compatível com regime de contribuições explicitamente cadastrado. CST 02 não migra silenciosamente para a alíquota geral.
- Prévia imutável com documentos, hash, pendências e exportação PDF/Excel. PDF apresenta divergências de base; Excel inclui itens compatíveis e não avaliados.
- Fechamento vinculado a arquivos exige conciliação expressa e ausência de bloqueios de integridade. Recuperação parcial e situação desconhecida impedem fechamento, sem impedir relatório de trabalho.
- Catálogo de produtos/serviços por cliente, reaproveitamento de itens observados e versões imutáveis; classificação conferida exige fundamento. Somente administrador publica versões.
- As classificações do catálogo não substituem documentos nem são automaticamente convertidas em regras ou alíquotas.

## Limites explícitos

A primeira entrega não é um motor fiscal nacional completo. Não acrescenta determinação legal de ISS, IPI, DIFAL/FCP, ST, IRRF, PCC ou INSS. Não acrescenta importadores NFS-e/CT-e. Os sete calculadores assistidos existentes mantêm seu escopo. Não existe preenchimento automático de receita tributável de ICMS especial a partir de NCM declarado.

O cadastro de produtos guarda classificação, não uma relação fixa produto→CFOP. A base de regras de auditoria existente continua separada do futuro catálogo de regras de determinação/apuração.

No Piselli, o perfil ainda não informa cumulatividade das contribuições. Por isso a base não é automaticamente inserida num regime presumido pelo software. O arquivo recuperado parcialmente também não comprova completude do movimento nem situação dos documentos.

## Próximas entregas necessárias

1. Perfil do estabelecimento ampliado: município, inscrições, regime de caixa/competência, atividades, condições de benefícios, anexos, RBT12 e folha histórica.
2. Contrato canônico de NFS-e, CT-e, notas de entrada e eventos de pagamento/crédito; finalidade da aquisição e atributos fiscais das partes.
3. Catálogo versionado de regras de determinação separado de regras de auditoria: UF/município, regimes, vigência, NCM+descrição/CEST, finalidade, CFOP, parte responsável, base/reduções, FCP, MVA/PMPF, fundamento e precedência explícita. Conflitos bloqueiam determinação; regra proposta não é fato fiscal.
4. Motor determinístico por item com valores decimais e trilha regra→base→tributo; razão de créditos, débitos, retenções, ajustes e transporte de saldos.
5. Adaptadores para conteúdo fiscal mantido, com revisão e publicação versionada. Atualizações não alteram versões históricas; possibilidade de recálculo comparativo.
6. Ampliar Simples além do Anexo I e integrar contabilidade ao Lucro Real. Evitar duplicidade entre DAS e tributos separados, retenções sofridas e obrigações de retenção, ST e diferencial já recolhido.
7. Suportar transição IBS/CBS por competência sem reaplicar regras atuais ao passado.

## Validação

Testes cobrem exemplo 1992 − 498 = 1494, ausências, CST 02, CFOPs não comerciais, duplicidade/conflitos, documentos cancelados, trimestre, exportação de prévia, hash obsoleto, bloqueio de fechamento e isolamento organizacional.

Na base do Piselli: 175 documentos, 33 linhas sem exclusão, 1 outra divergência, 777 compatíveis. Dados reais permanecem fora do Git.
