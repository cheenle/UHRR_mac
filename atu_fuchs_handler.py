"""
atu_fuchs_handler.py — Fuchs ATU WebSocket Handler for MRRC Server

Provides a dedicated WebSocket endpoint (/atu) that:
1. Accepts ESP32-S3 ATU connections
2. Relays commands between browser UI and ATU
3. Bridges ATR1000 SWR readings to ATU during tuning
"""

import json
import logging
from tornado.websocket import WebSocketHandler

logger = logging.getLogger("fuchs_atu")


class FuchsATUHandler(WebSocketHandler):
    """WebSocket handler for ESP32-S3 Fuchs ATU V3.0."""

    atu_connection = None
    browser_connections = set()
    active_tune = None

    def check_origin(self, origin):
        return True

    def open(self):
        logger.info(f"ATU WS connection from {self.request.remote_ip}")

    def on_message(self, message):
        try:
            msg = json.loads(message)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON: {message[:100]}")
            return

        if "evt" in msg:
            FuchsATUHandler._broadcast_to_browsers(msg)
            self._handle_atu_event(msg)
        elif "cmd" in msg:
            self._handle_browser_command(msg)
        else:
            logger.warning(f"Unknown message format: {msg}")

    def on_close(self):
        if self is FuchsATUHandler.atu_connection:
            logger.info("ATU ESP32-S3 disconnected")
            FuchsATUHandler.atu_connection = None
        else:
            FuchsATUHandler.browser_connections.discard(self)

    def _handle_atu_event(self, msg):
        evt = msg.get("evt")
        if evt == "tune_progress":
            FuchsATUHandler.active_tune = {
                "state": msg.get("state"),
                "servo_pos": msg.get("servo_pos"),
                "waiting_for_swr": True,
            }
            self._request_swr_from_atr1000()
        elif evt == "tune_done":
            FuchsATUHandler.active_tune = None
            logger.info(f"Tune complete: SWR={msg.get('swr_final')}")

    def _handle_browser_command(self, msg):
        cmd = msg.get("cmd")
        if FuchsATUHandler.atu_connection is None:
            self.write_message(json.dumps({
                "evt": "error", "message": "ATU not connected"
            }))
            return

        if cmd == "tune_start":
            swr_data = self._read_atr1000_swr()
            if swr_data:
                msg["swr"] = swr_data["swr"]
                msg["fwd_pwr_w"] = swr_data["fwd_pwr_w"]

        FuchsATUHandler.atu_connection.write_message(json.dumps(msg))

    def _read_atr1000_swr(self):
        try:
            from atr1000_tuner import get_atr1000_reading
            data = get_atr1000_reading()
            if data:
                return {"swr": data.swr, "fwd_pwr_w": data.fwd_pwr}
        except ImportError:
            logger.warning("ATR1000 module not available")
        except Exception as e:
            logger.error(f"ATR1000 read error: {e}")
        return None

    def _request_swr_from_atr1000(self):
        swr_data = self._read_atr1000_swr()
        if swr_data and FuchsATUHandler.atu_connection:
            FuchsATUHandler.atu_connection.write_message(json.dumps({
                "cmd": "swr_update",
                "swr": swr_data["swr"],
                "fwd_pwr_w": swr_data["fwd_pwr_w"],
            }))

    @classmethod
    def _broadcast_to_browsers(cls, msg):
        for browser in list(cls.browser_connections):
            try:
                browser.write_message(json.dumps(msg))
            except Exception:
                cls.browser_connections.discard(browser)


def register_fuchs_atu(app):
    """Register Fuchs ATU WebSocket endpoint with Tornado app."""
    app.add_handlers(r".*", [(r"/atu", FuchsATUHandler)])
    logger.info("Fuchs ATU WebSocket endpoint registered at /atu")
