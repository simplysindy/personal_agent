#!/usr/bin/env python3
"""Simple HTTP server for the frontend."""

import http.server
import socketserver
import os
from pathlib import Path

PORT = 5173
DIRECTORY = Path(__file__).parent.parent / "frontend"

os.chdir(DIRECTORY)

Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Frontend server running at http://localhost:{PORT}")
    print(f"Serving files from: {DIRECTORY}")
    print("Press Ctrl+C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
