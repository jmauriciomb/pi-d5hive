from flask import Flask, request, jsonify
import os
import subprocess
import sys
import socket

app = Flask(__name__)

hostname = socket.gethostname()
ENV = "render" if hostname[:4] == "srv-" else "flask"

print(f"Environment: {ENV}, host: {hostname}")



@app.route('/')
def home():
    return open('dashboard.html').read()

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/jb_gtfs', methods=['POST'])
def jb_gtfs():
    try:
        proc = subprocess.Popen(
            [sys.executable, 'JB_GTFS.py'],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        return jsonify({"status": "started", "pid": proc.pid}), 200
    except Exception as e:
        return jsonify({"status": "exception", "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)