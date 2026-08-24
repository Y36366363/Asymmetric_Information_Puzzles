from __future__ import annotations

import argparse
import errno
import json
import mimetypes
import threading
import webbrowser
from http.client import HTTPConnection
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlparse

from aip.ui.registry import LocalGameService, build_default_registry


STATIC_ROOT = files("aip.ui").joinpath("static")
MAX_REQUEST_BYTES = 1_000_000
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
        "form-action 'self'; object-src 'none'; frame-ancestors 'none'"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


class AIPRequestHandler(BaseHTTPRequestHandler):
    service = LocalGameService(build_default_registry())

    def _security_headers(self) -> None:
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlparse(self.path).path
        if path == "/api/games":
            self._json({"games": self.service.games()})
            return
        if path == "/api/health":
            self._json({"status": "ok", "application": "aip-game-lobby"})
            return
        if path.startswith("/api/sessions/"):
            session_id = path.removeprefix("/api/sessions/")
            self._handle_value(lambda: {"state": self.service.snapshot(session_id)})
            return
        asset = "index.html" if path == "/" else path.removeprefix("/")
        self._static(asset)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlparse(self.path).path
        try:
            body = self._read_json()
        except ValueError as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        if path == "/api/sessions":
            game_id = str(body.get("gameId", ""))
            options = body.get("options", {})
            if not isinstance(options, dict):
                self._json({"error": "options must be an object"}, HTTPStatus.BAD_REQUEST)
                return
            self._handle_value(lambda: self.service.create_session(game_id, options))
            return
        if path.startswith("/api/sessions/") and path.endswith("/actions"):
            session_id = path.removeprefix("/api/sessions/").removesuffix("/actions")
            action = str(body.get("action", ""))
            payload = body.get("payload", {})
            if not isinstance(payload, dict):
                self._json({"error": "payload must be an object"}, HTTPStatus.BAD_REQUEST)
                return
            self._handle_value(
                lambda: {"state": self.service.act(session_id, action, payload)}
            )
            return
        self._json({"error": "route not found"}, HTTPStatus.NOT_FOUND)

    def _handle_value(self, operation) -> None:
        try:
            self._json(operation())
        except ValueError as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def _read_json(self) -> dict[str, object]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("request body must be valid JSON") from error
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise ValueError(
                f"request body must be between 0 and {MAX_REQUEST_BYTES} bytes"
            )
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError) as error:
            raise ValueError("request body must be valid JSON") from error
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _static(self, asset: str) -> None:
        if ".." in Path(asset).parts:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        resource = STATIC_ROOT.joinpath(asset)
        if not resource.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = resource.read_bytes()
        content_type = mimetypes.guess_type(asset)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def _is_existing_aip_server(host: str, port: int) -> bool:
    connection = HTTPConnection(host, port, timeout=0.5)
    try:
        connection.request("GET", "/api/health")
        response = connection.getresponse()
        payload = json.loads(response.read())
        return payload.get("application") == "aip-game-lobby"
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    finally:
        connection.close()


def serve(host: str = "127.0.0.1", port: int = 8765, *, open_browser: bool = True) -> None:
    try:
        server = ThreadingHTTPServer((host, port), AIPRequestHandler)
    except OSError as error:
        if error.errno != errno.EADDRINUSE:
            raise
        if _is_existing_aip_server(host, port):
            url = f"http://{host}:{port}"
            print(f"AIP 游戏大厅已经在运行：{url}")
            if open_browser:
                webbrowser.open(url)
            return
        server = ThreadingHTTPServer((host, 0), AIPRequestHandler)
        print(f"端口 {port} 已被其他程序占用，已自动改用空闲端口。")
    url = f"http://{host}:{server.server_port}"
    print(f"AIP 游戏大厅已启动：{url}")
    print("按 Ctrl+C 结束游戏服务器。")
    if open_browser:
        threading.Timer(0.25, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AIP local playable game lobby")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args(argv)
    serve(args.host, args.port, open_browser=not args.no_open)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
