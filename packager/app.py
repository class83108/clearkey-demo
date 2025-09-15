import os
import json
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer


PORT = int(os.getenv("PORT", "8080"))


def run_pack(in_path: str, out_dir: str, kid_hex: str, key_hex: str) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["IN"] = in_path
    env["OUT"] = out_dir
    env["KID_HEX"] = kid_hex
    env["KEY_HEX"] = key_hex
    proc = subprocess.run(
        ["/bin/sh", "/work/pack.sh"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self._json(200, {"status": "ok"})
            return
        self._json(404, {"error": "not found"})

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        if self.path != "/pack":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = self.rfile.read(length)
            req = json.loads(data.decode("utf-8"))
        except Exception:
            self._json(400, {"error": "invalid json"})
            return

        input_rel = req.get("input_rel_path")  # e.g. uploads/xxx.mp4
        output_rel = req.get("output_rel_dir")  # e.g. encrypted/123
        kid_hex = req.get("kid_hex")
        key_hex = req.get("key_hex")

        if not all([input_rel, output_rel, kid_hex, key_hex]):
            self._json(400, {"error": "missing fields"})
            return

        in_path = f"/work/media/{input_rel}"
        out_dir = f"/work/media/{output_rel}"

        os.makedirs(out_dir, exist_ok=True)

        code, out, err = run_pack(in_path, out_dir, kid_hex, key_hex)
        if code != 0:
            self._json(500, {"status": "failed", "stdout": out, "stderr": err, "code": code})
            return

        self._json(200, {"status": "ok", "mpd": f"{output_rel}/stream.mpd", "stdout": out})


def main():
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
