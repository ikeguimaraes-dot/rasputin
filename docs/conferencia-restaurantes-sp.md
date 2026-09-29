# Conferência documental de restaurantes em SP

Motor 1.2.0; parser 1.1.0; política `sp-restaurante-2026.09.29.1`.

A nova conferência automática abrange perfis de Lucro Presumido ou Real em SP, para documentos de 01/01/2026 até a captura normativa de 29/09/2026. Datas posteriores são sinalizadas como não avaliadas, até revisão da base. Não substitui as regras aprovadas do escritório e não determina imposto recolhido.

## Importação e evidências

O layout de Conferência de Saídas é reconhecido pela combinação exata de cabeçalhos, incluindo grupos ICMS/IPI/PIS/COFINS. Nome da empresa e período não alteram a assinatura reutilizável. As colunas de CNPJ/nome são do destinatário, nunca do emitente. O usuário confirma o mapeamento na interface.

A recuperação BIFF8 conserva o sistema de datas 1900/1904 e formatos de célula. Arquivos recuperados continuam parciais. Linhas sem descrição ou valor obrigatório são descartadas com motivo e localização; ausência nunca vira zero. Não se infere autorização da nota, modelo 55/65, consumidor final ou condição de contribuinte do destinatário.

## Checagens automáticas de revisão

- D01: CFOP 5405 versus CST 60 e destaque de ICMS próprio; destaque em baixa 5927.
- D02: bebidas do antigo Anexo X em ST após sua revogação em janeiro de 2026; vinho da posição 2204 em ST.
- D03: NCM de bebida alcoólica com 4% em venda de optante pelo regime especial de alimentação.
- D04: alíquota superior a 25% em venda; descrições de refeições com 18%/25% em optante; possível alimentação em NF-e 55 com destaque. A descrição é indício para revisão, não classificador definitivo.
- D05: conflitos restritos entre descrição e NCM (água, vodka, alimentos/entrega codificados como vinho, indicações de bebidas e espumante). Nenhuma sugestão altera automaticamente o NCM.
- D06: diferenças de CST entre PIS/COFINS e CST 02 com alíquota básica. Sem regime de contribuições informado no Lucro Presumido, 0,65%/3% são somente referência explicitamente identificada; não determinam tributação nem benefício por NCM.

CST 40/41 com valor de ICMS é inconsistência documental. CEST `0000000` na planilha exige conferência com o original, pois pode representar campo ausente na exportação. Gorjeta não é tratada automaticamente como mercadoria com NCM inválido. IPI não informado gera checagem não avaliada, em vez de assumir não contribuinte.

Não existe regra geral que zere ICMS em 5949, 5919 ou 5929. Devolução 5202 permanece identificada no descritivo e não recebe automaticamente a alíquota de uma venda. Não se presume que toda bebida tenha a mesma alíquota, nem que toda operação de restaurante tenha direito a 4%.

## Fontes e limites

- [CFOP e CST, RICMS/SP Anexo V](https://legislacao.fazenda.sp.gov.br/Paginas/l6an5.aspx).
- [Artigo 274: documento do substituído](https://legislacao.fazenda.sp.gov.br/Paginas/art274.aspx).
- [Portaria SRE 64/2025](https://legislacao.fazenda.sp.gov.br/Paginas/Portaria-SRE-64-de-2025.aspx) e [CAT 68/2019, Anexo X e art. 2º](https://legislacao.fazenda.sp.gov.br/Paginas/Portaria-CAT-68-de-2019.aspx).
- [RC 24368/2021](https://legislacao.fazenda.sp.gov.br/Paginas/RC24368_2021.aspx): exclusão das bebidas alcoólicas do benefício. Seu percentual histórico não é usado como percentual atual.
- [Decreto 51.597/2007](https://legislacao.fazenda.sp.gov.br/Paginas/dec51597.aspx) e [RC 33063/2025, publicada em junho/2026](https://legislacao.fazenda.sp.gov.br/Paginas/RC33063_2025.aspx): 4%, com regras específicas do modelo fiscal; a NF-e 55 não autoriza destaque pelo regime de alimentação.
- [RICMS/SP, artigos 52 a 56](https://legislacao.fazenda.sp.gov.br/Paginas/art052.aspx).
- [RC 18590/2018](https://legislacao.fazenda.sp.gov.br/Paginas/RC18590_2018.aspx): baixa de estoque.
- [CST e tabelas de EFD-Contribuições](https://www.gov.br/receitafederal/pt-br/canais_atendimento/fale-conosco/empresa/sped/efd-contribuicoes/efd-contribuicoes-codigos-de-situacao-tributaria-cst-e-demais-tabelas-da-escrituracao).

As fontes e a versão da política entram no hash do resultado. Documentos, perfis, catálogo e regras são preservados nas análises; reemissão utiliza os resultados salvos. A tela e os relatórios mostram itens por CFOP, natureza, categoria declarada e alíquota, inclusive itens sem apontamento. Não somar esses valores como faturamento mensal: há devoluções, baixas e documentos referentes a operações anteriores.

Os testes são sintéticos. Planilhas de clientes e relatórios reais permanecem no armazenamento privado, fora do Git.
