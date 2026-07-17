# Integração MCP

No TALOS, o agente externo é a IA. O servidor `talos-freecad-mcp` expõe ferramentas estruturadas e
envia a execução para o Workbench aberto no FreeCAD.

## Pré-requisitos

- FreeCAD 1.1.1 aberto com o Workbench **TALOS MCP** ativo;
- `.venv` preparada conforme [installation.md](installation.md);
- executável `.venv\Scripts\talos-freecad-mcp.exe` disponível.

Sem a GUI, `health`, descoberta de capacidades e receitas funcionam normalmente.
Operações CAD retornam erro estruturado de ponte indisponível.

## Configuração

O repositório já contém `.mcp.json` para Claude Code. Registro manual:

```powershell
claude mcp add talos -- <projeto>\.venv\Scripts\talos-freecad-mcp.exe
```

Codex, em `~/.codex/config.toml`:

```toml
[mcp_servers.talos]
command = "C:\\caminho\\do\\projeto\\.venv\\Scripts\\talos-freecad-mcp.exe"
```

Cursor, em `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "talos": {
      "command": "C:/caminho/do/projeto/.venv/Scripts/talos-freecad-mcp.exe"
    }
  }
}
```

## Fluxo recomendado

1. Busque cartões compactos com `search_cad_capabilities` ou receitas com
   `available_cad_recipes`.
2. Carregue os contratos escolhidos com `describe_cad_capabilities`.
3. Use `inspect_cad_model` para obter contexto, validação e medidas em uma única
   chamada; ative detalhes, dependências ou vistas somente quando necessários.
4. Para uma leitura isolada, use `execute_cad_read_tool` com a capacidade
   registrada correspondente.
5. Para uma mutação, use `request_cad_tool` e repita o mesmo `request_id` até o
   estado terminal.
6. Para duas a oito mutações, prefira `submit_cad_plan` e acompanhe com
   `get_cad_plan_status`.
7. Valide o documento e meça o resultado.
8. Capture `isometric`, `front`, `top` e `right` de uma vez com
   `cad.capture_views`. Use `cad.capture_view` apenas quando uma vista basta.
9. Use `cad.capture_section_view` com plano e offset quando precisar inspecionar
   o interior sem alterar a geometria.
10. Consulte `get_mcp_performance_snapshot` ao otimizar uma sessão; os tokens
    são estimados por bytes e não substituem a medição do cliente.
11. Exporte STL ou STEP somente para um destino autorizado pelo usuário.

`search_cad_capabilities` aceita consulta vazia para paginação estável, filtros
`families` e `risks`, `limit` de até 20 e `cursor`. O resultado não inclui schemas
e permanece pequeno. `describe_cad_capabilities` aceita até 16 nomes únicos e
preserva a ordem pedida. `available_cad_tools` é o endpoint completo legado.

`inspect_cad_model` limita a inspeção a oito objetos. A seleção atual tem
prioridade, seguida por objetos recentes e pela primeira página do contexto. A
resposta marca `state_consistent=false` se o `DocumentStateToken` mudar entre a
primeira e a última leitura. Isso evita validar uma mistura de estados.

`get_mcp_performance_snapshot` mantém no máximo 128 chamadas recentes e nunca
retém argumentos. Ele separa tempo do MCP, ida e volta do bridge, fila da GUI,
espera de aprovação e execução no FreeCAD. Os dados desaparecem quando o
processo MCP termina.

Receitas disponíveis: `mounting_plate`, `flange`, `rectangular_pad`,
`stepped_shaft` e `flat_pulley`.

## Comportamentos importantes

- mutações seguem a opção de aprovação visível no painel;
- exportações são sempre manuais;
- argumentos inválidos falham antes da geometria;
- referências ambíguas nunca são escolhidas por palpite;
- erros retornam `code`, `category`, `retryable`, `safe_state_restored` e
  `suggested_actions`;
- `safe_state_restored=null` exige reler o contexto antes de qualquer nova
  mutação;
- capturas orientadas restauram a câmera e a preferência de animação ao final;
- cortes visuais não substituem um plano de clipping já ativo no FreeCAD;
- operações longas podem levar mais de um minuto;
- telemetria não contém conteúdo do pedido nem timestamps de parede;
- `cad.undo` desfaz a última transação confirmada;
- toda ação entra na auditoria local.

`cad.create_through_hole` atravessa o sólido inteiro por padrão. Para furar
somente um ressalto, informe `z_min` e `z_max` em coordenadas globais.

## Problemas comuns

| Sintoma | Ação |
| --- | --- |
| Ponte indisponível | abrir o FreeCAD e ativar **TALOS MCP** |
| `pending_confirmation` parado | responder no painel; aprovação automática só cobre mutações compensáveis |
| Ferramenta desconhecida | refazer `search_cad_capabilities` e descrever o contrato escolhido |
| Objeto ambíguo | selecionar ou informar nome único |
| Arquivo de exportação existente | usar `overwrite=true` apenas com autorização |

`retryable=true` indica que existe uma recuperação segura descrita nas ações;
não autoriza repetir mutações sem reler o estado. Falhas de transporte são
tratadas como ambíguas porque a conexão pode cair depois da execução.
