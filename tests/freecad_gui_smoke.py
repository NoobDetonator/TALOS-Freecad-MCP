from pathlib import Path
import os
import sys
import traceback


project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets


result_path = Path(os.environ["AICAD_GUI_RESULT"])
screenshot_path = Path(os.environ["AICAD_GUI_SCREENSHOT"])


def inspect() -> None:
    try:
        for document_name in list(App.listDocuments()):
            App.closeDocument(document_name)

        assert "AICadWorkbench" in Gui.listWorkbenches()
        Gui.activateWorkbench("AICadWorkbench")
        QtWidgets.QApplication.processEvents()

        main_window = Gui.getMainWindow()
        dock = main_window.findChild(QtWidgets.QDockWidget, "AICadChatDock")
        assert dock is not None and dock.isVisible()
        prompt = dock.findChild(QtWidgets.QPlainTextEdit, "AICadPrompt")
        send = dock.findChild(QtWidgets.QPushButton, "AICadSend")
        apply_button = dock.findChild(QtWidgets.QPushButton, "AICadApply")
        history = dock.findChild(QtWidgets.QTextBrowser, "AICadHistory")
        assert all(widget is not None for widget in (prompt, send, apply_button, history))

        prompt.setPlainText("resumo")
        send.click()
        QtWidgets.QApplication.processEvents()
        assert "Nenhum documento CAD está ativo" in history.toPlainText()

        prompt.setPlainText("caixa 10 x 20 x 30 nome GuiSmokeBox")
        send.click()
        QtWidgets.QApplication.processEvents()
        assert App.ActiveDocument is None
        assert apply_button.isVisible()
        apply_button.click()
        QtWidgets.QApplication.processEvents()
        assert App.ActiveDocument is not None
        assert len(App.ActiveDocument.Objects) == 1
        assert App.ActiveDocument.UndoCount == 1
        assert "criada e validada" in history.toPlainText()
        assert main_window.grab().save(str(screenshot_path), "PNG")

        Gui.Selection.addSelection(App.ActiveDocument.Objects[0])
        prompt.setPlainText("seleção")
        send.click()
        QtWidgets.QApplication.processEvents()
        assert "Seleção atual (1): GuiSmokeBox" in history.toPlainText()
        Gui.Selection.clearSelection()

        prompt.setPlainText("validar")
        send.click()
        QtWidgets.QApplication.processEvents()
        assert "validado sem erros" in history.toPlainText()

        prompt.setPlainText("desfazer")
        send.click()
        QtWidgets.QApplication.processEvents()
        assert len(App.ActiveDocument.Objects) == 1
        apply_button.click()
        QtWidgets.QApplication.processEvents()
        assert len(App.ActiveDocument.Objects) == 0
        assert "foi desfeita" in history.toPlainText()

        App.closeDocument(App.ActiveDocument.Name)
        result_path.write_text("FREECAD_GUI_SMOKE_OK", encoding="utf-8")
        QtWidgets.QApplication.exit(0)
    except Exception:
        result_path.write_text(
            "FREECAD_GUI_SMOKE_FAILED\n" + traceback.format_exc(),
            encoding="utf-8",
        )
        traceback.print_exc()
        QtWidgets.QApplication.exit(1)


QtCore.QTimer.singleShot(1500, inspect)
