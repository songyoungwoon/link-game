#!/usr/bin/env python3
# Copyright 2026 Song Youngwoon
# SPDX-License-Identifier: Apache-2.0
"""Verify real two-process NPC travel with disposable databases and native rendering."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def free_ports():
    probes = [socket.socket(socket.AF_INET, socket.SOCK_STREAM) for _ in range(2)]
    try:
        for probe in probes:
            probe.bind(("127.0.0.1", 0))
        return [probe.getsockname()[1] for probe in probes]
    finally:
        for probe in probes:
            probe.close()


def wait_ready(process, port):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Disposable NPC server stopped during startup.")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=.2):
                return
        except OSError:
            time.sleep(.05)
    raise RuntimeError("Disposable NPC server did not become ready.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", type=Path, default=ROOT.parent / "link" / "build" / "native" / "Release" / "LINK.exe")
    parser.add_argument("--probe", type=Path, help="Optional native observer/world probe executable")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "npc-qa")
    args = parser.parse_args(argv)
    browser, output = args.browser.resolve(strict=True), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = output / "desktop.json"
    # Avoid reading a previous successful report if the new browser fails early.
    report.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="link-npc-journey-") as directory:
        temporary = Path(directory)
        worlds = temporary / "worlds"
        ports = free_ports()
        old_addresses = ["link://127.0.0.1:8010/traveler-a", "link://127.0.0.1:8011/traveler-b"]
        addresses = ["link://127.0.0.1:" + str(port) + "/traveler-" + side for port, side in zip(ports, ("a", "b"))]
        key = temporary / "peer.key"
        key.write_text(secrets.token_hex(32) + "\n", encoding="ascii")
        processes, handles = [], []
        try:
            for index, side in enumerate(("a", "b")):
                world = worlds / ("traveler-" + side)
                shutil.copytree(ROOT / "worlds" / ("traveler-" + side), world)
                manifest = world / "world.link"
                text = manifest.read_text(encoding="utf-8")
                config_text = (ROOT / "configs" / ("npc-traveler-" + side + ".json")).read_text(encoding="utf-8")
                for original, replacement in zip(old_addresses, addresses):
                    text = text.replace(original, replacement)
                    config_text = config_text.replace(original, replacement)
                manifest.write_text(text, encoding="utf-8")
                config = temporary / (side + ".json")
                config.write_text(config_text, encoding="utf-8")
                log = (output / ("server-" + side + ".log")).open("w", encoding="utf-8")
                handles.append(log)
                processes.append(subprocess.Popen([sys.executable, "-u", str(ROOT / "server" / "npc_server.py"),
                    "--config", str(config), "--database", str(temporary / (side + ".sqlite3")),
                    "--peer-key-file", str(key), "--worlds", str(worlds)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT))
            for process, port in zip(processes, ports):
                wait_ready(process, port)
            if args.probe:
                for side, address in zip(("a", "b"), addresses):
                    probe = subprocess.run([str(args.probe.resolve(strict=True)), "--address", address, "--worlds", str(worlds), "--duration-ms", "1000"], capture_output=True, text=True, encoding="utf-8", timeout=15)
                    (output / ("probe-" + side + ".log")).write_text(probe.stdout + probe.stderr, encoding="utf-8")
                    if probe.returncode:
                        raise RuntimeError("Native NPC observer/world probe failed for " + side + ".")
            with (output / "desktop.log").open("w", encoding="utf-8") as log:
                result = subprocess.run([str(browser), "--worlds", str(worlds), "--open", addresses[0],
                    "--profile-directory", str(temporary / "profiles"), "--npc-smoke", str(report)], cwd=browser.parent,
                    stdout=log, stderr=subprocess.STDOUT, timeout=90)
            if result.returncode or not report.exists() or not json.loads(report.read_text(encoding="utf-8"))["passed"]:
                raise RuntimeError("Native desktop NPC round-trip check failed. See desktop.log and desktop.json.")
            print(report.read_text(encoding="utf-8"))
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
            for handle in handles:
                handle.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print("NPC verification failed: " + str(error), file=sys.stderr)
        raise SystemExit(1)
