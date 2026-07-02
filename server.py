import http.server
import socketserver
import json
import os
import socket
import urllib.parse
import sys

PORT = int(os.environ.get('PORT', 3000))

# In-memory Database
polls = [
    {
        "id": "poll-1",
        "title": "是否同意 115 學年度社課時間調整為每週三晚上 7:00 至 9:00？",
        "description": "因考量幹部與社員課程安排，提議調整社課時間。",
        "options": ["同意", "不同意", "無意見"],
        "status": "draft",  # "draft" | "open" | "closed"
        "votes": [0, 0, 0],
        "votedTokens": []
    }
]
active_poll_id = "poll-1"
ADMIN_TOKEN = "ndhu-tkd-admin-secret-token-8888"

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.254.254.254', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class VotingHandler(http.server.BaseHTTPRequestHandler):
    def end_headers(self):
        # Allow CORS for development if needed
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def check_admin_auth(self):
        auth_header = self.headers.get('Authorization', '')
        if auth_header == f"Bearer {ADMIN_TOKEN}":
            return True
        self.send_response(401)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps({"error": "未經授權：需要管理員權限！"}).encode('utf-8'))
        return False

    def serve_static(self, file_path, content_type):
        full_path = os.path.join(os.path.dirname(__file__), 'public', file_path)
        if not os.path.exists(full_path) or os.path.isdir(full_path):
            # Fallback to index.html for SPA behavior
            full_path = os.path.join(os.path.dirname(__file__), 'public', 'index.html')
            content_type = 'text/html; charset=utf-8'

        try:
            with open(full_path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Server error: {str(e)}")

    def do_GET(self):
        url_parsed = urllib.parse.urlparse(self.path)
        path = url_parsed.path
        query = urllib.parse.parse_qs(url_parsed.query)

        # Static routing
        if path == '/' or path == '/index.html':
            self.serve_static('index.html', 'text/html; charset=utf-8')
            return
        elif path == '/admin' or path == '/admin.html':
            self.serve_static('admin.html', 'text/html; charset=utf-8')
            return
        elif path == '/style.css':
            self.serve_static('style.css', 'text/css; charset=utf-8')
            return
        elif path == '/logo.png' or path.endswith('.png'):
            self.serve_static(clean_path, 'image/png')
            return

        # API routing
        if path == '/api/server-info':
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"ip": get_local_ip(), "port": PORT}).encode('utf-8'))
            return

        elif path == '/api/poll/active':
            token_list = query.get('token', [''])
            client_token = token_list[0]
            
            global active_poll_id
            active_poll = next((p for p in polls if p["id"] == active_poll_id), None)
            
            if not active_poll:
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"poll": None}).encode('utf-8'))
                return

            has_voted = client_token in active_poll["votedTokens"] if client_token else False
            
            poll_data = {
                "poll": {
                    "id": active_poll["id"],
                    "title": active_poll["title"],
                    "description": active_poll["description"],
                    "options": active_poll["options"],
                    "status": active_poll["status"],
                    "hasVoted": has_voted
                }
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(poll_data).encode('utf-8'))
            return

        elif path == '/api/admin/polls':
            if not self.check_admin_auth():
                return
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"polls": polls, "activePollId": active_poll_id}).encode('utf-8'))
            return

        elif path == '/api/admin/results':
            if not self.check_admin_auth():
                return
            active_poll = next((p for p in polls if p["id"] == active_poll_id), None)
            if not active_poll:
                self.send_response(404)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "目前無啟用中的投票！"}).encode('utf-8'))
                return

            results = {
                "title": active_poll["title"],
                "options": active_poll["options"],
                "votes": active_poll["votes"],
                "totalVotes": len(active_poll["votedTokens"])
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(results).encode('utf-8'))
            return

        # Serve from public directory if it matches any other file
        if not path.startswith('/api/'):
            clean_path = path.lstrip('/')
            self.serve_static(clean_path, 'application/octet-stream')
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        url_parsed = urllib.parse.urlparse(self.path)
        path = url_parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8')) if post_data else {}
        except Exception:
            data = {}

        if path == '/api/auth/login':
            username = data.get('username')
            password = data.get('password')
            if username == 'user' and password == 'user1234':
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "token": ADMIN_TOKEN}).encode('utf-8'))
            else:
                self.send_response(401)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "帳號或密碼錯誤！"}).encode('utf-8'))
            return

        elif path == '/api/poll/vote':
            poll_id = data.get('pollId')
            option_index = data.get('optionIndex')
            token = data.get('token')

            if not token:
                self.send_response(400)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "遺失選民辨識碼！"}).encode('utf-8'))
                return

            poll = next((p for p in polls if p["id"] == poll_id), None)
            if not poll:
                self.send_response(404)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "找不到該投票主題！"}).encode('utf-8'))
                return

            if poll["status"] != "open":
                self.send_response(400)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "投票目前未開放或已結束！"}).encode('utf-8'))
                return

            if token in poll["votedTokens"]:
                self.send_response(400)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "您在此投票中已經投過票囉！"}).encode('utf-8'))
                return

            try:
                idx = int(option_index)
            except (TypeError, ValueError):
                idx = -1

            if idx < 0 or idx >= len(poll["options"]):
                self.send_response(400)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "無效的選項！"}).encode('utf-8'))
                return

            # Record vote anonymously
            poll["votes"][idx] += 1
            poll["votedTokens"].append(token)

            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "message": "投票成功，感謝您的參與！"}).encode('utf-8'))
            return

        elif path == '/api/admin/polls':
            if not self.check_admin_auth():
                return
            title = data.get('title')
            description = data.get('description', '')
            options = data.get('options', [])

            if not title or len(options) < 2:
                self.send_response(400)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "標題與至少兩個選項為必填！"}).encode('utf-8'))
                return

            cleaned_options = [o.strip() for o in options if o.strip()]
            if len(cleaned_options) < 2:
                self.send_response(400)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "至少需要兩個有效選項！"}).encode('utf-8'))
                return

            import time
            new_poll = {
                "id": f"poll-{int(time.time() * 1000)}",
                "title": title,
                "description": description,
                "options": cleaned_options,
                "status": "draft",
                "votes": [0] * len(cleaned_options),
                "votedTokens": []
            }
            polls.append(new_poll)
            
            self.send_response(201)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(new_poll).encode('utf-8'))
            return

        elif path.startswith('/api/admin/polls/') and path.endswith('/reset'):
            if not self.check_admin_auth():
                return
            parts = path.split('/')
            poll_id = parts[4]
            poll = next((p for p in polls if p["id"] == poll_id), None)
            if not poll:
                self.send_response(404)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "找不到該投票主題！"}).encode('utf-8'))
                return

            poll["votes"] = [0] * len(poll["options"])
            poll["votedTokens"] = []
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "poll": poll}).encode('utf-8'))
            return

        self.send_error(404, "Not Found")

    def do_PUT(self):
        url_parsed = urllib.parse.urlparse(self.path)
        path = url_parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        put_data = self.rfile.read(content_length)
        try:
            data = json.loads(put_data.decode('utf-8')) if put_data else {}
        except Exception:
            data = {}

        if path.startswith('/api/admin/polls/') and path.endswith('/active'):
            if not self.check_admin_auth():
                return
            parts = path.split('/')
            poll_id = parts[4]
            
            poll = next((p for p in polls if p["id"] == poll_id), None)
            if not poll:
                self.send_response(404)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "找不到該投票主題！"}).encode('utf-8'))
                return

            global active_poll_id
            active_poll_id = poll_id
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "activePollId": active_poll_id}).encode('utf-8'))
            return

        elif path.startswith('/api/admin/polls/') and path.endswith('/status'):
            if not self.check_admin_auth():
                return
            parts = path.split('/')
            poll_id = parts[4]
            status = data.get('status')

            if status not in ['open', 'closed', 'draft']:
                self.send_response(400)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "無效的投票狀態！"}).encode('utf-8'))
                return

            poll = next((p for p in polls if p["id"] == poll_id), None)
            if not poll:
                self.send_response(404)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "找不到該投票主題！"}).encode('utf-8'))
                return

            poll["status"] = status
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "poll": poll}).encode('utf-8'))
            return

        self.send_error(404, "Not Found")

    def do_DELETE(self):
        url_parsed = urllib.parse.urlparse(self.path)
        path = url_parsed.path

        if path.startswith('/api/admin/polls/'):
            if not self.check_admin_auth():
                return
            parts = path.split('/')
            poll_id = parts[4]

            global polls, active_poll_id
            poll_index = next((i for i, p in enumerate(polls) if p["id"] == poll_id), -1)
            
            if poll_index == -1:
                self.send_response(404)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "找不到該投票主題！"}).encode('utf-8'))
                return

            polls.pop(poll_index)
            if active_poll_id == poll_id:
                active_poll_id = polls[0]["id"] if len(polls) > 0 else None

            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "activePollId": active_poll_id}).encode('utf-8'))
            return

        self.send_error(404, "Not Found")

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

if __name__ == '__main__':
    server_address = ('', PORT)
    httpd = ThreadingHTTPServer(server_address, VotingHandler)
    print(f"====================================================")
    print(f"東華跆拳社匿名投票系統 (Python 版) 啟動成功！")
    print(f"本機存取網址: http://localhost:{PORT}")
    print(f"局域網存取網址: http://{get_local_ip()}:{PORT}")
    print(f"====================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)
