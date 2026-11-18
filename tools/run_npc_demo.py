#!/usr/bin/env python3
# Copyright 2026 Song Youngwoon
# SPDX-License-Identifier: Apache-2.0
"""Run two independent local LINK NPC servers until Ctrl+C (no third-party packages)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    configs = [ROOT / "configs" / ("npc-traveler-" + side + ".json") for side in ("a", "b")]
    ports = []
    for path in configs:
        config = json.loads(path.read_text(encoding="utf-8"))
        authority = config["authority"]
        if not authority.startswith("link://127.0.0.1:"):
            raise ValueError("The two-server launcher requires loopback demo configs. For separate PCs, run server/npc_server.py on each host.")
        ports.append(int(authority.split(":", 2)[2].split("/", 1)[0]))
    if len(set(ports)) != 2:
        raise ValueError("The NPC worlds must use two different ports.")
    # Reserve both briefly before launching. A later bind race still fails safely:
    # only child processes created here are stopped; existing services are untouched.
    reservations = []
    try:
        for port in ports:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            reservations.append(probe)
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind(("127.0.0.1", port))
    finally:
        for probe in reservations:
            probe.close()
    data = ROOT / "data"
    data.mkdir(exist_ok=True)
    key = data / "npc-peer.key"
    try:
        with key.open("x", encoding="ascii") as output:
            output.write(secrets.token_hex(32) + "\n")
    except FileExistsError:
        pass
    processes = []
    try:
        for side, config in zip(("a", "b"), configs):
            processes.append(subprocess.Popen([sys.executable, "-u", str(ROOT / "server" / "npc_server.py"),
                "--config", str(config), "--database", str(data / ("npc-" + side + ".sqlite3")),
                "--peer-key-file", str(key), "--host", "127.0.0.1"], cwd=ROOT))
        print("NPC journey: two LINK servers, separate durable databases.", flush=True)
        print("Open link://127.0.0.1:" + str(ports[0]) + "/traveler-a in the latest LINK Browser.", flush=True)
        print("Liora continues walking while all browsers are closed. Ctrl+C stops both servers.", flush=True)
        while True:
            for process in processes:
                result = process.poll()
                if result is not None:
                    raise RuntimeError("An NPC server stopped (exit " + str(result) + "). Check the server message above.")
            time.sleep(.2)
    except KeyboardInterrupt:
        print("Stopping the NPC demo...", flush=True)
        # Console Ctrl+C is delivered to both child processes too. Give SQLite
        # cleanup time before terminating only this launcher's remaining children.
        until = time.monotonic() + 5
        while time.monotonic() < until and any(process.poll() is None for process in processes):
            time.sleep(.05)
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print("NPC demo could not start: " + str(error), file=sys.stderr)
        raise SystemExit(1)
