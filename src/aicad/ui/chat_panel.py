from __future__ import annotations

from html import escape

from aicad.core.chat_commands import ChatCommand, format_tool_result, parse_chat_command
from aicad.core.tool_registry import ToolRisk
from aicad.runtime import get_tool_registry


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
    pending: list[ChatCommand] = []

    def append_assistant(message: str) -> None:
        history.append(f"<p><b>AI CAD:</b> {message}</p>")

    def set_pending(command: ChatCommand | None) -> None:
        pending.clear()
        if command is not None:
            pending.append(command)
        waiting = command is not None
        confirmation.setVisible(waiting)
        prompt.setEnabled(not waiting)
        send.setEnabled(not waiting)

    def execute(command: ChatCommand, confirmed: bool = False) -> None:
        try:
            result = registry.execute(
                command.tool_name,
                command.arguments,
                confirmed=confirmed,
            )
            append_assistant(format_tool_result(command.tool_name, result))
            if command.tool_name in {"cad.create_box", "cad.undo"}:
                active_gui_document = Gui.activeDocument()
                if active_gui_document is not None:
                    active_gui_document.activeView().viewAxonometric()
                    active_gui_document.activeView().fitAll()
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
        command = pending[0]
        set_pending(None)
        execute(command, confirmed=True)

    def cancel_pending() -> None:
        if not pending:
            return
        set_pending(None)
        append_assistant("Operação cancelada; o documento não foi alterado.")

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
