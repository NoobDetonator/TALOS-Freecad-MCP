from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from aicad.bridge.dispatcher import BridgeDispatcher
from aicad.bridge.protocol import BridgeRequest, BridgeResponse
from aicad.bridge.session import (
    BridgeSessionRecord,
    BridgeSessionStore,
    default_session_store,
)
from aicad.bridge.transport import LocalTcpBridgeServer
from aicad.core.tool_registry import ToolRegistry
from aicad.runtime import get_tool_registry


GUI_REQUEST_TIMEOUT_SECONDS = 120.0
GUI_DISPATCH_INTERVAL_MS = 50


class GuiBridgeController:
    """Own the local bridge lifecycle from the FreeCAD GUI thread."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        session_store: BridgeSessionStore | None = None,
    ) -> None:
        self._confirmation_listener: Callable[[BridgeRequest], None] | None = None
        self._dispatcher = BridgeDispatcher(
            registry,
            on_confirmation_requested=self._request_confirmation,
            request_timeout=GUI_REQUEST_TIMEOUT_SECONDS,
        )
        self._server = LocalTcpBridgeServer(self._dispatcher.submit)
        self._session_store = session_store or default_session_store()
        self._session_record: BridgeSessionRecord | None = None
        self._timer: object | None = None

    @property
    def is_running(self) -> bool:
        return self._server.is_running and self._session_record is not None

    @property
    def session_record(self) -> BridgeSessionRecord:
        if self._session_record is None:
            raise RuntimeError("The GUI bridge has not been started.")
        return self._session_record

    def set_confirmation_listener(
        self,
        listener: Callable[[BridgeRequest], None],
    ) -> None:
        self._confirmation_listener = listener

    def start(self) -> BridgeSessionRecord:
        if self.is_running:
            return self.session_record

        from PySide import QtCore, QtWidgets

        application = QtWidgets.QApplication.instance()
        if application is None:
            raise RuntimeError("The GUI bridge requires a running Qt application.")
        endpoint = self._server.start()
        try:
            record = self._session_store.publish(endpoint)
        except Exception:
            self._server.stop()
            raise

        timer = QtCore.QTimer(application)
        timer.setInterval(GUI_DISPATCH_INTERVAL_MS)
        timer.timeout.connect(self._tick)
        timer.start()
        application.aboutToQuit.connect(stop_gui_bridge)

        self._session_record = record
        self._timer = timer
        return record

    def resolve_confirmation(
        self,
        request_id: UUID,
        *,
        approved: bool,
    ) -> BridgeResponse:
        return self._dispatcher.resolve_confirmation(
            request_id,
            approved=approved,
        )

    def stop(self) -> None:
        timer = self._timer
        if timer is not None:
            timer.stop()
        self._timer = None

        self._dispatcher.close()
        self._server.stop()
        record = self._session_record
        self._session_record = None
        if record is not None:
            self._session_store.clear(record.session_id)

    def _tick(self) -> None:
        self._dispatcher.expire_requests()
        self._dispatcher.process_next()

    def _request_confirmation(self, request: BridgeRequest) -> None:
        listener = self._confirmation_listener
        if listener is None:
            raise RuntimeError("No GUI confirmation listener is available.")
        listener(request)


_controller: GuiBridgeController | None = None


def get_or_start_gui_bridge(
    confirmation_listener: Callable[[BridgeRequest], None],
) -> GuiBridgeController:
    global _controller

    if _controller is None:
        _controller = GuiBridgeController(get_tool_registry())
    _controller.set_confirmation_listener(confirmation_listener)
    if not _controller.is_running:
        _controller.start()
    return _controller


def get_gui_bridge() -> GuiBridgeController | None:
    return _controller


def stop_gui_bridge() -> None:
    global _controller

    controller = _controller
    _controller = None
    if controller is not None and controller.is_running:
        controller.stop()
