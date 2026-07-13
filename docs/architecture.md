# Arquitetura inicial

## Princípio

A IA planeja, a camada de ferramentas autoriza, o FreeCAD executa e o validador verifica.

## Componentes

1. **Interface** — painel lateral dentro do FreeCAD. O modo atual interpreta um
   vocabulário local fechado e não executa texto como código.
2. **Orquestrador de IA** — futuramente usa a Responses API e outros provedores.
3. **ToolRegistry** — catálogo único, schemas, handlers, validação de argumentos
   e bloqueio de ferramentas de risco sem confirmação explícita.
4. **Application** — conecta todas as especificações a uma única interface de
   adaptador CAD, sem importar FreeCAD.
5. **FreeCadAdapter** — camada que importa o FreeCAD sob demanda, lê o documento
   e executa mutações transacionais.
6. **Runtime** — fornece a mesma instância do registro ao chat e ao MCP dentro de
   cada processo.
7. **MCP** — publica o catálogo compartilhado. Enquanto não existe a ponte com a
   GUI, permite somente a tentativa de execução de ferramentas de leitura.
8. **Validação** — recomputa e verifica estados de erro e validade das formas.

## Regra de dependência

`aicad.core` não importa FreeCAD ou Qt. A UI, o MCP e os provedores dependem do núcleo. Somente `aicad.adapters.freecad_adapter` conversa diretamente com o FreeCAD.

## Fluxo atual do chat

1. O texto é convertido por um parser local em nome de ferramenta e argumentos
   estruturados.
2. O `ToolRegistry` confere ferramenta, schema, campos extras, tipos, limites e
   risco.
3. Ferramentas de leitura são executadas imediatamente.
4. Ferramentas `modify` só são executadas depois da confirmação no painel.
5. O handler conectado chama o `FreeCadAdapter`.
6. O resultado estruturado volta ao painel para apresentação.

Não existe ferramenta de Python genérico e o parser não possui caminho para
avaliar código.

## Contrato de mutação

Para criar uma caixa, o adaptador:

1. valida dimensões finitas, positivas e o nome;
2. garante que o histórico de desfazer do documento esteja habilitado;
3. abre uma transação nomeada;
4. cria o objeto e recalcula;
5. valida a forma e o documento ainda dentro da transação;
6. confirma em caso de sucesso ou aborta e recalcula em caso de falha.

O teste de integração exige que a transação aumente a pilha de desfazer e que o
objeto desapareça depois de `undo`.

## Limite atual do MCP

O servidor MCP e a GUI já constroem o registro pela mesma composição. Porém, o
servidor MCP roda em outro processo e ainda não tem acesso seguro à thread Qt do
FreeCAD. Por isso, mutações via MCP são recusadas mesmo que estejam no catálogo.
Essa restrição evita criar um segundo caminho de execução sem confirmação.

## Próxima etapa técnica

Criar uma ponte local autenticada entre o servidor MCP e o processo gráfico do
FreeCAD, com fila única de comandos, execução na thread principal do Qt,
solicitação de confirmação para riscos e retorno estruturado. Depois disso,
integrar um provedor de IA sem mudar os schemas nem os handlers CAD.
