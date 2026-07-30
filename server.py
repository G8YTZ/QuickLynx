#!/usr/bin/env python3
"""
QuickLynx local server.

Serves quicklynx.html at http://localhost:PORT/ - deliberately just
this, nothing more. Running from a real HTTP origin (rather than a
bare file:// page) avoids inconsistent, browser-specific file://
security restrictions, while staying entirely local: nothing here
talks to the internet itself, and nothing runs on the Lynx Pi.

Also proxies BATC's own wideband chat page (see proxy_chat below) so
it can be embedded in an iframe - BATC's server sends an
X-Frame-Options header that blocks being framed from a different
origin (confirmed directly: the page loads fine as its own tab, but
appears blank when embedded, matching that behaviour exactly).
Fetching it server-side and re-serving it from localhost sidesteps
this cleanly, since the browser's same-origin frame check only cares
about where the framed DOCUMENT was actually served from - not where
its own sub-resources (CSS, JS, the chat's live Socket.IO connection)
subsequently load from, which continue to talk to BATC directly and
are unaffected by this.

Uses only the Python standard library - no dependencies to install,
matching the project's own "no build step" goal.
"""
import http.server
import socketserver
import webbrowser
import sys
import os
import urllib.request
import urllib.error

PORT = 8765
BATC_CHAT_URL = "https://eshail.batc.org.uk/wb/chat/"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)

    def log_message(self, format, *args):
        # Quieter than the default - one line per request is enough
        print(f"[quicklynx] {self.address_string()} - {format % args}")

    def do_GET(self):
        if self.path.split('?', 1)[0] == '/proxy/chat':
            self.proxy_chat()
            return
        super().do_GET()

    def proxy_chat(self):
        """Fetch BATC's chat page server-side and re-serve it from
        localhost, with a <base> tag injected so every relative URL
        in the page (stylesheets, scripts, and critically any
        relative Socket.IO connection URL the page's own JS might
        construct) resolves against BATC's real site rather than
        this local /proxy/chat path - UNVERIFIED specifically for the
        Socket.IO connection itself, since that depends on how the
        page's own JS builds its URL internally, which wasn't
        available to inspect directly. If chat loads but doesn't
        connect, that JS-level detail is the first thing to check.
        """
        try:
            req = urllib.request.Request(
                BATC_CHAT_URL,
                headers={
                    # Some servers reject urllib's default UA outright
                    "User-Agent": "Mozilla/5.0 (compatible; QuickLynx local proxy)",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                html = resp.read().decode(charset, errors="replace")

            base_tag = f'<base href="{BATC_CHAT_URL}">'
            if "<head>" in html:
                html = html.replace("<head>", "<head>" + base_tag, 1)
            elif "<head " in html:
                # a <head> tag with attributes - insert just after its closing >
                idx = html.index("<head ")
                close = html.index(">", idx) + 1
                html = html[:close] + base_tag + html[close:]
            else:
                html = base_tag + html

            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            # Deliberately NOT forwarding BATC's own response headers
            # (including their X-Frame-Options) - this is a fresh
            # response from localhost, which is the whole point.
            self.end_headers()
            self.wfile.write(body)

        except urllib.error.URLError as e:
            self.send_error(502, f"Could not reach BATC's chat page: {e.reason}")
        except Exception as e:
            self.send_error(502, f"Chat proxy error: {e}")

def main():
    port = PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Ignoring invalid port argument {sys.argv[1]!r}, using default {PORT}")

    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        url = f"http://127.0.0.1:{port}/quicklynx.html"
        print(f"QuickLynx running at {url}")
        print("Press Ctrl+C to stop.")
        try:
            webbrowser.open(url)
        except Exception:
            pass  # not fatal if this fails - the printed URL still works
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")

if __name__ == "__main__":
    main()
