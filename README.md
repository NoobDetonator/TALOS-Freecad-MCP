# AI CAD Workbench

Base inicial de um ambiente CAD paramétrico controlável por chat interno e por MCP.

O primeiro protótipo usa o FreeCAD como motor de modelagem, visualização e documento. A camada `aicad` concentra ferramentas determinísticas, permissões e a integração local com MCP.

## Estado atual

- Workbench `AI CAD` carregável pelo ambiente portátil já preparado.
- Painel lateral com chat local determinístico e sem dependência de provedor.
- Comandos para ler documento e seleção, validar, criar uma caixa e desfazer.
- Confirmação explícita na interface antes de criar ou desfazer.
- `ToolRegistry` único para catálogo, schemas, validação e política de risco.
- Chat e MCP conectados ao mesmo registro e ao mesmo adaptador.
- Criação de caixa em transação validada e registrada no histórico de desfazer.
- Ponte MCP–GUI autenticada, restrita ao loopback e executada pela thread Qt.
- Mutações MCP pendentes até confirmação explícita no painel.
- Testes unitários, teste transacional no FreeCADCmd e fluxo MCP gráfico automatizado.
- Instalação reproduzível e isolada para Windows.

## Preparação

Execute no PowerShell:

```powershell
.\scripts\setup.ps1
```

Se o ambiente já estiver preparado, não execute o setup novamente.

Depois, abra o FreeCAD com:

```powershell
.\scripts\iniciar.ps1
```

O ambiente `AI CAD` aparecerá na lista de Workbenches.

## Chat local

O painel aceita, nesta fase, um vocabulário fechado. Exemplos:

```text
resumo
seleção
validar
caixa 10 x 20 x 30 nome MinhaCaixa
desfazer
```

Leituras são executadas imediatamente. Criação e desfazer mostram o plano e só
executam depois do clique em **Confirmar operação**. Texto livre não vira Python
nem é enviado a um serviço externo.

## MCP local

Com o FreeCAD aberto por `scripts/iniciar.ps1`, o servidor MCP encontra a sessão
gráfica por um registro efêmero no diretório local do usuário. Leituras percorrem
a ponte e são executadas na thread principal do Qt. Para qualquer ferramenta
`modify`, `request_cad_tool` retorna `pending_confirmation`; somente o clique no
painel autoriza a execução.

O mesmo `request_id`, nome e argumentos podem ser reenviados para consultar o
resultado sem repetir a mutação. Reutilizar o ID com conteúdo diferente é
rejeitado.

O transporte escuta apenas em `127.0.0.1`, usa token aleatório por sessão,
mensagens limitadas e timeout. O token não é gravado no repositório nem exibido
em logs.

## Testes

```powershell
.\scripts\testar.ps1
```

A suíte abre e fecha automaticamente uma instância isolada do FreeCAD para
confirmar que o Workbench aparece, o painel abre e o fluxo criar/desfazer funciona.

## Segurança

Chaves de API nunca devem ser salvas no repositório. Nenhuma chave é solicitada
na fase atual. Quando um provedor realmente for integrado, a credencial será
armazenada no cofre do Windows. A pasta `.runtime`, ambientes, downloads,
arquivos CAD gerados e segredos são ignorados pelo Git.

O MCP não acessa o adaptador diretamente. Toda chamada passa pelo protocolo
tipado, pela validação do `ToolRegistry`, pela fila da GUI e, nas mutações, pela
confirmação visual.

## Arquitetura

Consulte [docs/architecture.md](docs/architecture.md),
[docs/product-vision.md](docs/product-vision.md) e
[docs/milestones.md](docs/milestones.md). O último contém o plano completo de
marcos e o roteiro para retomar o projeto em outro computador ou chat.
