#!/usr/bin/env python3
"""
Master Launcher: MCP Server + Valkyrie Bots
==========================================
Starter både Chigwell's Telegram MCP server og dine C2/Verify bots.
Alt kører lokalt uden Docker.
"""

import os
import sys
import subprocess
import threading
import time
import signal

# Colors for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'

def log(msg, color=RESET):
    print(f"{color}[MASTER] {msg}{RESET}")

processes = []

def start_mcp_server():
    """Start Chigwell's MCP server."""
    log("Starting MCP Server...", BLUE)
    cmd = [sys.executable, "main.py"]
    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))
    
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env
    )
    processes.append(('MCP Server', proc))
    return proc

def start_bots():
    """Start Valkyrie bots."""
    log("Starting Valkyrie Bots...", BLUE)
    cmd = [sys.executable, "valkyrie_bot_launcher.py", "--all"]
    env = os.environ.copy()
    
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env
    )
    processes.append(('Valkyrie Bots', proc))
    return proc

def stream_output(name, proc):
    """Stream output from process."""
    try:
        for line in proc.stdout:
            print(f"[{name}] {line.rstrip()}")
    except:
        pass

def shutdown(signum=None, frame=None):
    """Shutdown all processes."""
    log("Shutting down all processes...", YELLOW)
    for name, proc in processes:
        log(f"Stopping {name}...", YELLOW)
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except:
            proc.kill()
    log("All processes stopped. Goodbye!", GREEN)
    sys.exit(0)

def main():
    """Main entry point."""
    log("=" * 60, GREEN)
    log("VALKYRIE TELEGRAM SUITE - LOCAL MODE", GREEN)
    log("MCP Server + C2 Bot + Verify Bot", GREEN)
    log("=" * 60, GREEN)
    
    # Check .env exists
    if not os.path.exists('.env'):
        log("ERROR: .env file not found!", RED)
        log("Please create .env with TELEGRAM_API_ID and TELEGRAM_API_HASH", RED)
        sys.exit(1)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    # Start MCP Server
    mcp_proc = start_mcp_server()
    time.sleep(2)  # Give MCP time to start
    
    # Start Bots
    bots_proc = start_bots()
    time.sleep(1)
    
    # Start output streaming threads
    threads = [
        threading.Thread(target=stream_output, args=('MCP', mcp_proc), daemon=True),
        threading.Thread(target=stream_output, args=('BOTS', bots_proc), daemon=True)
    ]
    for t in threads:
        t.start()
    
    log("All systems running! Press Ctrl+C to stop.", GREEN)
    log("Commands:", BLUE)
    log("  - /c2_status    : Check C2 bot status", BLUE)
    log("  - /verify_status: Check Verify bot status", BLUE)
    log("  - /alive        : Send ALIVE message", BLUE)
    log("  - /beacon       : Simulate beacon (test)", BLUE)
    
    try:
        # Wait for processes
        while True:
            for name, proc in processes:
                if proc.poll() is not None:
                    log(f"{name} exited with code {proc.returncode}", RED)
                    shutdown()
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()

if __name__ == '__main__':
    main()
