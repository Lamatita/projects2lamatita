import http.server
import socketserver
import os
import sys

PORT = 5000

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Allow SharedArrayBuffer for WebAssembly/pygbag
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        super().end_headers()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"Starting server on port {PORT}...")
    sys.stdout.flush()
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()
