# Arquitetura inicial

## Princípio

A IA planeja, a camada de ferramentas autoriza, o FreeCAD executa e o validador verifica.

## Componentes

1. **Interface** — painel lateral dentro do FreeCAD. O modo atual interpreta um
   vocabulário local fechado e não executa texto como código.
2. **Orquestrador de IA** — planeja por um contrato neutro; adaptadores concretos virão depois.
3. **ToolRegistry** — catálogo único, schemas, handlers, validação de argumentos
   e bloqueio de ferramentas de risco sem confirmação explícita.
4. **Application** — conecta todas as especificações a uma única interface de
   adaptador CAD, sem importar FreeCAD.
5. **FreeCadAdapter** — camada que importa o FreeCAD sob demanda, lê o documento
   e executa mutações transacionais.
6. **Runtime** — fornece a mesma instância do registro ao chat e ao MCP dentro de
   cada processo.
7. **MCP** — publica o catálogo compartilhado e envia leituras e solicitações de
   mutação para a mesma fila segura da GUI.
8. **Validação** — recomputa e verifica estados de erro e validade das formas.

## Protocolo da ponte local

O primeiro bloco do M2 define envelopes versionados em
`aicad.bridge.protocol`, independentemente do transporte local. Uma request
carrega `protocol_version`, `request_id`, `tool_name`, `arguments` e `source`.
Uma response carrega um resultado estruturado, o estado
`pending_confirmation` ou um erro categorizado.

O envelope rejeita campos extras, versões desconhecidas e nomes que não tenham
o formato de ferramenta CAD. Depois do parse, nome e argumentos passam pelo
mesmo `ToolRegistry` usado pelo chat e pelo MCP. Essa validação não executa o
handler e não substitui a confirmação exigida para ferramentas de risco.

O protocolo não importa FreeCAD, Qt, transporte ou servidor MCP.

## Transporte local da ponte

O transporte inicial do M2 usa TCP em loopback IPv4, com `127.0.0.1` como host
padrão. O listener recusa endereços externos e usa uma porta efêmera escolhida
pelo sistema operacional. A escolha mantém o protótipo testável no Windows com
a biblioteca padrão e sem acoplar o protocolo a uma API exclusiva do sistema.

Cada sessão gera um token aleatório de alta entropia, mantido fora de logs e
oculto na representação do endpoint. O token é comparado antes de qualquer
request chegar ao handler. A descoberta do endpoint usa um registro efêmero no
diretório de runtime local do usuário, fora do repositório.

As mensagens usam JSON UTF-8 precedido por um tamanho de 32 bits, com limite de
1 MiB e timeout configurável. JSON inválido, valores não finitos, frames vazios
ou grandes demais são recusados. O servidor pode receber conexões em threads de
transporte, mas o handler da GUI somente enfileira requests. Um timer do Qt
transfere toda execução CAD para a thread principal.

## Descoberta da sessão

A GUI publica o endpoint autenticado como `bridge-session.json` no runtime do usuário. O
registro contém versão do protocolo, ID da sessão, host, porta, token, PID e
timestamp UTC. A escrita usa arquivo temporário, `fsync` e substituição atômica;
o arquivo recebe permissões restritas conforme o suporte do sistema operacional.

Diretório ou arquivo de sessão em symlink são recusados. No encerramento, a GUI
remove o registro somente se o `session_id` ainda corresponder à sua sessão. Se
outra instância já tiver publicado um endpoint novo, ele é preservado.

`AICAD_RUNTIME_DIR` permite informar diretamente o diretório de descoberta.
Sem essa variável, a pasta de runtime do usuário fornecida por `platformdirs` é
usada. Ausência ou corrupção do registro produz erro controlado e nunca inicia
instalações automaticamente.

## Dispatcher da GUI

O transporte entrega requests ao `BridgeDispatcher`, que pode ser chamado por
workers, mas pertence à thread em que foi criado. `process_next`, confirmação,
expiração e fechamento só podem ocorrer nessa thread, que é a thread principal
do Qt na integração com o painel.

Leituras aguardam na fila até `process_next` executá-las pelo `ToolRegistry`.
Mutações retornam `pending_confirmation` sem executar e são apresentadas uma por
vez. `resolve_confirmation` confere novamente estado e prazo antes de chamar o
registro com autorização explícita.

Repetir a mesma request com o mesmo ID funciona como polling idempotente. Reusar
o ID com conteúdo diferente é rejeitado. Requests expiradas permanecem
inexecutáveis, inclusive se uma confirmação antiga chegar depois do timeout.

## Planejamento independente de provedor

`aicad.orchestration` define o primeiro bloco do M3 sem importar FreeCAD, Qt ou
qualquer SDK de IA. O contrato `ProviderRequest` envia somente a mensagem atual,
contexto JSON limitado e as definições de ferramentas permitidas para a rodada.

A resposta exige intenção, suposições, passos ordenados e chamadas estruturadas.
`AiOrchestrator` rejeita respostas malformadas, IDs duplicados, ferramentas fora
da allowlist, argumentos inválidos e chamadas acima do limite configurado.

Cada chamada aceita passa novamente por `ToolRegistry.validate_arguments` e
recebe o risco autoritativo do registro. O plano marca se haverá confirmação,
mas não executa handlers; texto retornado pelo provedor nunca vira código.

Este corte faz uma única rodada de planejamento. Adaptador concreto, ativação do
provedor, execução de leituras, confirmação de mutações, cancelamento e loop
iterativo permanecem fora dele até suas políticas serem implementadas e testadas.

## Credenciais de provedor

`CredentialStore` mantém identificadores de provedor separados das chaves e usa
`keyring` como única fronteira de persistência. A chave OpenAI é associada a uma
conta específica dentro do serviço `ai-cad-workbench` no cofre do sistema.

O painel oferece configuração/substituição em campo mascarado e remoção
explícita. Abrir o painel não acessa o cofre nem bloqueia a thread Qt; consultas
ocorrem apenas nas ações de configuração ou remoção. O valor não aparece em
widgets, logs ou mensagens. Erros do backend são
categorizados sem incluir o erro bruto, que poderia carregar material sensível.

O retorno programático usa `SecretStr`. Salvar a chave apenas prepara o futuro
adaptador e não ativa rede, modelo ou execução de ferramentas.

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

## Fluxo atual do MCP

O servidor MCP e a GUI usam a mesma composição do registro em seus processos.
`request_cad_tool` valida a chamada, descobre a sessão gráfica e envia o envelope
para a fila pertencente à GUI.

Leituras retornam o resultado executado na thread Qt. Mutações retornam
`pending_confirmation`, aparecem no painel e só usam `confirmed=True` depois do
clique do usuário. Repetir a request com o mesmo ID consulta o resultado.

## Próxima etapa técnica

Implementar o primeiro adaptador de provedor sobre o contrato neutro, definir sua
configuração e integrar o plano ao painel. A execução de leituras e o envio de
mutações para confirmação continuarão usando o registro e a ponte existentes,
com cancelamento e limites de iteração adicionados antes de ativar o provedor.
