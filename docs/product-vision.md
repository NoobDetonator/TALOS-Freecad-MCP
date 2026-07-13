# Visão do produto

Um ambiente CAD paramétrico local, auditável e independente de provedor, controlável por conversa e por agentes externos.

## Primeiro nicho

Peças mecânicas simples para impressão 3D e fabricação leve:

- suportes;
- caixas e tampas;
- adaptadores;
- flanges;
- placas e gabaritos.

## Fluxo obrigatório

1. Entender intenção e restrições.
2. Expor suposições.
3. Criar plano de operações.
4. Gerar prévia.
5. Aplicar em uma transação.
6. Recalcular e validar.
7. Confirmar ou reverter.

## Estado da fase 1

O primeiro corte funcional cobre o ciclo completo para uma caixa paramétrica:

- o Workbench aparece e abre o painel de chat;
- o pedido local é convertido em uma chamada estruturada;
- o plano é mostrado antes da mutação;
- a interface exige confirmação explícita;
- a caixa é criada em transação, recalculada e validada;
- a transação é reversível por `desfazer`;
- a mesma lista de capacidades é usada pelo chat e pelo MCP;
- mutações MCP continuam bloqueadas até existir confirmação pela GUI.

Ainda não há interpretação por modelo de IA, credencial de provedor, exportação
para fabricação ou ponte entre processos. Esses itens não são simulados pelo
protótipo: permanecem explicitamente fora do corte atual.

## Diferenciais pretendidos

- operação local e privada;
- histórico completo das ações da IA;
- mesma capacidade no chat e via MCP;
- modelos paramétricos editáveis;
- validação antes de exportar ou fabricar.
