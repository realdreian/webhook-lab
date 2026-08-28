# Regras do agente

Regras de como trabalhar neste repositório. Não descrevem o produto —
isso está em `openspec/`.

## Escopo

1. Execute apenas as tasks pedidas. Marque o checkbox ao concluir.
2. Não implemente comportamento de tasks futuras. Se uma task exigir
   algo que pertence a outra, pare e avise em vez de adiantar.
3. Ao desviar do fluxo padrão, diga que desviou e por quê.

## Verificação

4. Verifique o ambiente antes de afirmar. Nunca assuma que um serviço
   ou dependência existe — cheque.
5. Task com "verify" significa executar. Escrever e presumir não conta.
6. Teste de integração usa o serviço real, não mock.
7. Teste que valida crescimento ou limite compara dois valores. Checar
   se o resultado existe ou é positivo não prova nada.
8. "Confirmar visualmente" é renderizar e olhar. Buscar o conteúdo da
   URL não é confirmação visual.

## Higiene

9. Dependência se declara em um lugar só.
10. Antes de editar doc ou spec, verifique se a informação já existe em
    outro lugar. Corrija no lugar em vez de duplicar.
11. `.gitignore` em todo projeto, antes do primeiro commit.
12. Dependências isoladas por projeto conforme a linguagem (venv no
    Python, node_modules local no JS). Nunca instalar global.
13. Estratégia de isolamento entre execuções de teste deve estar
    documentada.

## Limpeza

14. Não deixe código morto, import não usado, arquivo vazio criado "por
    precaução" ou print de debug.
15. Comentário explica o código, não o processo. Nada de narrar a sessão ("aqui eu corrijo o bug") nem referenciar números de task, specs ou planos — essas referências ficam órfãs quando a change é arquivada. Se o teste cobre um cenário, cite o cenário pelo nome, não pelo número.
16. Se algo foi criado e não é mais usado, apague no mesmo commit.

## Documentação

17. Escreva no idioma do documento que está editando, não no idioma do
    prompt.
18. Todo README abre explicando o problema que o projeto resolve, em
    uma frase, e traz os comandos para instalar, rodar e testar. Só
    depois vêm decisões e configuração.



