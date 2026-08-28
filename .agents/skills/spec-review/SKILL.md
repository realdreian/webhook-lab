---
name: spec-review
description: Revisa código implementado contra a spec e o design, apontando divergências sem corrigir. Use após concluir um grupo de tasks.
---

# Revisão contra spec

Você audita. Não corrige, a menos que seja pedido depois.

## Passos

1. Leia a spec e o design.md da change em questão.
2. Leia o diff das tasks implementadas.
3. Confronte um contra o outro.

## O que procurar

- Requisito da spec sem cobertura de teste
- Teste que passa sem provar nada: valida existência ou sinal em vez
  de comparar valores; usa mock onde a spec pede serviço real
- Comportamento implementado que pertence a outra task ou capability
- Informação duplicada entre arquivos
- Código morto, import não usado, print de debug, arquivo vazio
- Instrução de verificação cumprida pela metade (buscar URL em vez de
  renderizar, escrever teste em vez de rodar)

## Formato da saída

Para cada achado:

- **Arquivo e linha**
- **O que diverge** da spec ou do design
- **Como verificar** que foi corrigido

Não corrija nada. Só aponte.

Após correções, rode a revisão uma segunda vez — correção introduz
desvio novo. Classifique cada achado como divergência de spec ou
higiene.

Encerre quando a passada não trouxer nenhuma divergência de spec.
Achado de higiene remanescente não impede o encerramento. Máximo de
três passadas: se ainda aparecer divergência de spec na terceira, o
problema está na spec, não no código — pare e relate isso.