"""An in-memory GitHub contents API, for the shared-work tests (no network)."""
import base64
import hashlib
import json
import urllib.parse


class FakeGitHub:
    def __init__(self, token='buono', repo='noi/Flamingos-dati', private=True):
        self.token, self.repo, self.private = token, repo, private
        self.files, self.commits = {}, []

    def __call__(self, method, url, headers, body=None, timeout=15):
        if headers.get('Authorization') != f'Bearer {self.token}':
            return 401, b'{"message":"Bad credentials"}'
        base = f'https://api.github.com/repos/{self.repo}'
        if not url.startswith(base):
            return 404, b'{"message":"Not Found"}'
        rest = url[len(base):].split('?')[0]
        if rest == '':
            return 200, json.dumps({'private': self.private}).encode()
        path = urllib.parse.unquote(rest[len('/contents/'):])
        if method == 'GET':
            if path not in self.files:
                return 404, b'{"message":"Not Found"}'
            data, sha = self.files[path]
            if 'raw' in headers.get('Accept', ''):
                return 200, data
            big = len(data) > 1_000_000
            return 200, json.dumps({'sha': sha, 'size': len(data), 'encoding': 'none' if big else 'base64',
                                    'content': '' if big else base64.b64encode(data).decode()}).encode()
        payload = json.loads(body)
        current = self.files.get(path)
        if current and payload.get('sha') != current[1]:
            return 409, b'{"message":"does not match sha"}'
        if not current and payload.get('sha'):
            return 422, b'{"message":"sha wasn\'t supplied"}'
        if current and 'sha' not in payload:
            return 422, b'{"message":"\\"sha\\" wasn\'t supplied."}'
        data = base64.b64decode(payload['content'])
        sha = hashlib.sha1(data+str(len(self.commits)).encode()).hexdigest()
        self.files[path] = (data, sha)
        self.commits.append((path, payload['message']))
        return (200 if current else 201), json.dumps({'content': {'sha': sha}}).encode()
