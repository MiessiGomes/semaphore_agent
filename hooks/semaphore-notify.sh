#!/usr/bin/env bash
# Send status update to semaphore daemon via Unix socket (Python one-liner).
set -euo pipefail
SOURCE="${1:?source}"
STATE="${2:?state}"
DETAIL="${3:-}"

python3 - "$SOURCE" "$STATE" "$DETAIL" <<'PY'
import json, os, socket, sys
source, state, detail = sys.argv[1:4]
runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
path = os.path.join(runtime, "semaphore_agent", "status.sock")
payload = json.dumps({"source": source, "state": state, "detail": detail}).encode()
try:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(2)
    s.connect(path)
    s.sendall(payload)
except OSError:
    sys.exit(0)
PY
