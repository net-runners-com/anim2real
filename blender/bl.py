#!/usr/bin/env python3
"""Send Python code to the running Blender MCP addon socket (localhost:9876).

Usage:
  bl.py path/to/script.py      # run a file inside Blender
  bl.py -c "import bpy; result={'n': len(bpy.data.objects)}"
Assign a JSON-serialisable dict to `result` to get data back.
"""
import json, os, socket, sys

HOST = os.environ.get("BLENDER_MCP_HOST", "localhost")
PORT = int(os.environ.get("BLENDER_MCP_PORT", "9878"))  # anim2real 専用 Blender（blender/start.sh）。anim は 9877


def send(code: str, timeout: float = 3600.0) -> dict:
    req = json.dumps({"type": "execute", "code": code, "strict_json": False}) + "\0"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect((HOST, PORT))
        s.sendall(req.encode())
        buf = bytearray()
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf.extend(chunk)
            if b"\0" in buf:
                break
    line, _, _ = buf.partition(b"\0")
    return json.loads(line.decode())


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "-c":
        code = sys.argv[2]
    elif len(sys.argv) >= 2:
        with open(sys.argv[1], encoding="utf-8") as f:
            code = f.read()
    else:
        code = sys.stdin.read()
    r = send(code)
    for k in ("stdout", "stderr"):
        if r.get(k):
            print(f"--- {k} ---\n{r[k]}", file=sys.stderr if k == "stderr" else sys.stdout)
    if r.get("status") != "ok":
        print("ERROR:", r.get("message"), file=sys.stderr)
        return 1
    res = r.get("result")
    if res is not None:
        print(json.dumps(res, ensure_ascii=False, indent=1, default=repr))
    return 0


if __name__ == "__main__":
    sys.exit(main())
