from __future__ import annotations

from html import escape

from aicad.bridge.protocol import (
    BridgeRequest,
    BridgeResponse,
    BridgeResponseStatus,
)
from aicad.core.chat_commands import ChatCommand, format_tool_result, parse_chat_command
from aicad.core.tool_registry import ToolRisk
from aicad.runtime import get_tool_registry
from aicad.ui.bridge_controller import GuiBridgeController, get_or_start_gui_bridge


DOCK_NAME = "AICadChatDock"


def show_chat_panel() -> None:
    import FreeCADGui as Gui
    from PySide import QtCore, QtWidgets

    main_window = Gui.getMainWindow()
    existing = main_window.findChild(QtWidgets.QDockWidget, DOCK_NAME)
    if existing is not None:
        existing.show()
        existing.raise_()
        return

    dock = QtWidgets.QDockWidget("AI CAD", main_window)
    dock.setObjectName(DOCK_NAME)
    dock.setAllowedAreas(
        QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea
    )

    container = QtWidgets.QWidget(dock)
    layout = QtWidgets.QVBoxLayout(container)

    status = QtWidgets.QLabel(
        "Modo local seguro • nenhuma chave de API configurada", container
    )
    status.setObjectName("AICadStatus")
    status.setWordWrap(True)

    history = QtWidgets.QTextBrowser(container)
    history.setObjectName("AICadHistory")
    history.setHtml(
        "<b>AI CAD pronto.</b><br>"
        "O chat local já pode ler o documento e preparar operações CAD seguras. "
        "Digite <code>ajuda</code> para ver os comandos."
    )

    prompt = QtWidgets.QPlainTextEdit(container)
    prompt.setObjectName("AICadPrompt")
    prompt.setPlaceholderText("Descreva a peça ou alteração desejada...")
    prompt.setMaximumHeight(100)

    send = QtWidgets.QPushButton("Enviar", container)
    send.setObjectName("AICadSend")

    confirmation = QtWidgets.QWidget(container)
    confirmation.setObjectName("AICadConfirmation")
    confirmation_layout = QtWidgets.QHBoxLayout(confirmation)
    confirmation_layout.setContentsMargins(0, 0, 0, 0)
    apply_button = QtWidgets.QPushButton("Confirmar operação", confirmation)
    apply_button.setObjectName("AICadApply")
    cancel_button = QtWidgets.QPushButton("Cancelar", confirmation)
    cancel_button.setObjectName("AICadCancel")
    confirmation_layout.addWidget(apply_button, 1)
    confirmation_layout.addWidget(cancel_button)
    confirmation.hide()

    registry = get_tool_registry()
    pending: list[ChatCommand | BridgeRequest] = []
    remote_confirmation_queue: list[BridgeRequest] = []
    bridge_controller: list[GuiBridgeController] = []

    def append_assistant(message: str) -> None:
        history.append(f"<p><b>AI CAD:</b> {message}</p>")

    def set_pending(
        command: ChatCommand | BridgeRequest | None,
    ) -> None:
        pending.clear()
        if command is not None:
            pending.append(command)
        waiting = command is not None
        confirmation.setVisible(waiting)
        prompt.setEnabled(not waiting)
        send.setEnabled(not waiting)

    def refresh_view(tool_name: str) -> None:
        if tool_name not in {"cad.create_box", "cad.undo"}:
            return
        active_gui_document = Gui.activeDocument()
        if active_gui_document is not None:
            active_gui_document.activeView().viewAxonometric()
            active_gui_document.activeView().fitAll()

    def describe_bridge_request(request: BridgeRequest) -> str:
        arguments = ", ".join(
            f"<code>{escape(str(name))}={escape(str(value))}</code>"
            for name, value in request.arguments.items()
        )
        if not arguments:
            arguments = "sem argumentos"
        return (
            "<b>Solicitação MCP recebida.</b><br>"
            f"Ferramenta: <code>{escape(request.tool_name)}</code><br>"
            f"Argumentos: {arguments}<br>"
            "A operação só será executada após sua confirmação."
        )

    def show_next_remote_confirmation() -> None:
        if pending or not remote_confirmation_queue:
            return
        request = remote_confirmation_queue.pop(0)
        append_assistant(describe_bridge_request(request))
        set_pending(request)

    def queue_bridge_confirmation(request: BridgeRequest) -> None:
        remote_confirmation_queue.append(request)
        show_next_remote_confirmation()

    def show_bridge_response(
        request: BridgeRequest,
        response: BridgeResponse,
    ) -> None:
        if response.status is BridgeResponseStatus.COMPLETED:
            append_assistant(format_tool_result(request.tool_name, response.result))
            refresh_view(request.tool_name)
            return
        message = (
            response.error.message
            if response.error is not None
            else f"Estado da solicitação MCP: {response.status}."
        )
        append_assistant(f"Solicitação MCP não executada: {escape(message)}")

    def execute(command: ChatCommand, confirmed: bool = False) -> None:
        try:
            result = registry.execute(
                command.tool_name,
                command.arguments,
                confirmed=confirmed,
            )
            append_assistant(format_tool_result(command.tool_name, result))
            refresh_view(command.tool_name)
        except (KeyError, PermissionError, RuntimeError, ValueError) as exc:
            append_assistant(f"Operação não executada: {escape(str(exc))}")

    def submit() -> None:
        text = prompt.toPlainText().strip()
        if not text:
            return
        history.append(f"<p><b>Você:</b> {escape(text)}</p>")
        prompt.clear()
        command = parse_chat_command(text)
        append_assistant(command.message)
        if command.tool_name is None:
            return
        spec = registry.get_spec(command.tool_name)
        if spec.risk is ToolRisk.READ:
            execute(command)
            return
        set_pending(command)

    def confirm_pending() -> None:
        if not pending:
            return
        operation = pending[0]
        set_pending(None)
        if isinstance(operation, ChatCommand):
            execute(operation, confirmed=True)
        elif bridge_controller:
            response = bridge_controller[0].resolve_confirmation(
                operation.request_id,
                approved=True,
            )
            show_bridge_response(operation, response)
        else:
            append_assistant("A ponte MCP não está disponível para confirmar.")
        show_next_remote_confirmation()

    def cancel_pending() -> None:
        if not pending:
            return
        operation = pending[0]
        set_pending(None)
        if isinstance(operation, ChatCommand):
            append_assistant("Operação cancelada; o documento não foi alterado.")
        elif bridge_controller:
            response = bridge_controller[0].resolve_confirmation(
                operation.request_id,
                approved=False,
            )
            show_bridge_response(operation, response)
        else:
            append_assistant("Solicitação MCP cancelada sem alterar o documento.")
        show_next_remote_confirmation()

    try:
        controller = get_or_start_gui_bridge(queue_bridge_confirmation)
        bridge_controller.append(controller)
        status.setText(
            "Modo local seguro • ponte MCP local ativa • nenhuma chave de API"
        )
    except (OSError, RuntimeError, ValueError) as exc:
        append_assistant(
            "Ponte MCP indisponível; o chat local continua ativo: "
            + escape(str(exc))
        )

    send.clicked.connect(submit)
    apply_button.clicked.connect(confirm_pending)
    cancel_button.clicked.connect(cancel_pending)
    layout.addWidget(status)
    layout.addWidget(history, 1)
    layout.addWidget(prompt)
    layout.addWidget(send)
    layout.addWidget(confirmation)
    dock.setWidget(container)
    main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
    dock.show()
