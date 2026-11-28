"""Official Sign in with ChatGPT (OSS plan usage), local OAuth and streaming."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import threading
import tempfile
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib import error, parse, request

from infrastructure.file_lock import FileLock

ISSUER = 'https://auth.openai.com'
AUTHORIZE = ISSUER + '/api/accounts/authorize'
TOKEN = ISSUER + '/api/accounts/oauth/token'
JWKS = ISSUER + '/.well-known/jwks.json'
RESOURCE = 'https://api.openai.com/v1'
DIRECT_SCOPE = 'chatgpt.tokens.use.direct'
SCOPES = 'openid profile email offline_access resource.invoke ' + DIRECT_SCOPE
CALLBACK = '/auth/callback'
USAGE = 'https://chatgpt.com/settings/usage'


class ChatGPTError(RuntimeError):
    def __init__(self, message, code='', status=None, request_id=''):
        super().__init__(message)
        self.code, self.status, self.request_id = code, status, request_id


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = request.build_opener(NoRedirect())
INFERENCE_LOCK = threading.Lock()


def open_request(req, timeout=30):
    try:
        return OPENER.open(req, timeout=timeout)
    except error.HTTPError as exc:
        try:
            data = json.loads(exc.read(65536))
            info = data.get('error', {})
            code = info.get('code', '') if isinstance(info, dict) else info
        except (ValueError, AttributeError):
            code = ''
        raise service_error(code, exc.code, exc.headers.get('x-request-id', '')) from None
    except (OSError, error.URLError):
        raise ChatGPTError('No se pudo conectar con ChatGPT. Revisa la conexión e inténtalo más tarde.') from None


def service_error(code='', status=None, request_id=''):
    messages = {
        'subscription_sharing_user_not_eligible': 'Esta cuenta o espacio de trabajo no admite el uso del plan de ChatGPT.',
        'subscription_sharing_usage_limit_exceeded': 'Límite de uso del plan de ChatGPT alcanzado. Revisa ' + USAGE,
        'subscription_sharing_usage_unavailable': 'No se pudo comprobar el uso del plan. Inténtalo más tarde.',
        'subscription_sharing_unsupported_capability': 'El modelo o la petición no es compatible con el plan de ChatGPT.',
        'invalid_grant': 'La sesión de ChatGPT ya no es válida. Vuelve a conectar tu cuenta.',
    }
    # Never include arbitrary server bodies or secrets in application logs.
    message = messages.get(code) or {401: 'ChatGPT no autorizó la sesión. Vuelve a conectar la cuenta.',
        403: 'ChatGPT denegó el acceso al plan.', 429: 'Límite de ChatGPT alcanzado. Revisa ' + USAGE,
        503: 'El servicio de ChatGPT no está disponible temporalmente.'}.get(status, 'ChatGPT no pudo completar la petición.')
    if status:
        message += f' (HTTP {status})'
    return ChatGPTError(message, code, status, request_id)


def json_request(url, *, form=None, token=None):
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = None
    if form is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        data = parse.urlencode(form).encode()
    with open_request(request.Request(url, data=data, headers=headers)) as response:
        return json.load(response)


def secure_directory():
    # Never store credentials next to the repository, recordings or OneDrive documents.
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData/Local')
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
        if not base.is_absolute():
            base = Path.home() / '.config'
    return base / 'estudio' / 'chatgpt'


def windows_protect(data, decrypt=False):
    """Use Windows DPAPI, bound to the current Windows user."""
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = Blob(len(data), buffer)
    target = Blob()
    fn = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ChatGPTError('No se pudieron proteger o leer las credenciales de ChatGPT.')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)


def token_fields(data, previous=None):
    previous = previous or {}
    scopes = data.get('scope', ' '.join(previous.get('scopes', []))).split()
    if not data.get('access_token') or str(data.get('token_type', '')).lower() != 'bearer':
        raise ChatGPTError('ChatGPT no devolvió credenciales válidas.')
    return {'access_token': data['access_token'], 'refresh_token': data.get('refresh_token') or previous.get('refresh_token', ''),
            'scopes': scopes, 'expires_at': time.time() + int(data['expires_in'])}


def validate_identity(id_token, client_id, nonce):
    import jwt
    key = jwt.PyJWKClient(JWKS, timeout=15).get_signing_key_from_jwt(id_token)
    claims = jwt.decode(id_token, key.key, algorithms=['RS256'], issuer=ISSUER, audience=client_id,
                        options={'require': ['exp', 'iss', 'aud', 'sub', 'nonce']})
    if claims['nonce'] != nonce or not claims['sub'] or (claims.get('azp', client_id) != client_id):
        raise ChatGPTError('No se pudo verificar la identidad de ChatGPT.')
    return claims


def authorization_callback(host_id, saved=None):
    saved = saved or {}
    state, nonce, verifier = (secrets.token_urlsafe(48) for _ in range(3))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    result = {}

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def log_message(self, *args):
            pass

        def do_GET(self):
            url = parse.urlsplit(self.path)
            query = parse.parse_qs(url.query)
            if url.path != CALLBACK or not hmac.compare_digest(query.get('state', [''])[0], state):
                self.send_error(400, 'Invalid callback')
                return
            if any(len(values) != 1 for values in query.values()):
                self.send_error(400, 'Invalid callback')
                return
            result.update({k: v[0] for k, v in query.items()})
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write('Puedes cerrar esta ventana y volver a Estudio.'.encode())

    with HTTPServer(('127.0.0.1', 0), Handler) as server:
        server.timeout = 1
        redirect = f'http://127.0.0.1:{server.server_port}{CALLBACK}'
        params = dict(client_id=saved.get('client_id', 'dynamic_agent_client'), ext_agent_host_id=host_id,
                      response_type='code', redirect_uri=redirect, scope=SCOPES, resource=RESOURCE,
                      state=state, nonce=nonce, code_challenge_method='S256', code_challenge=challenge)
        if saved:
            if saved.get('id_token'):
                params['id_token_hint'] = saved['id_token']
            if saved.get('email'):
                params['login_hint'] = saved['email']
            if DIRECT_SCOPE not in saved.get('scopes', []):
                params['prompt'] = 'consent'
        else:
            params['agent_name_hint'] = 'Estudio'
        if not webbrowser.open(AUTHORIZE + '?' + parse.urlencode(params)):
            raise ChatGPTError('No se pudo abrir el navegador para conectar ChatGPT.')
        deadline = time.monotonic() + 180
        while not result and time.monotonic() < deadline:
            server.handle_request()
    if not result or result.get('error') or not result.get('code'):
        raise ChatGPTError('Inicio de sesión cancelado o caducado. Vuelve a intentarlo.')
    client_id = result.get('client_id') or saved.get('client_id')
    if not client_id or not client_id.startswith('oaiapp_') or (saved and client_id != saved['client_id']):
        raise ChatGPTError('Registro de ChatGPT no válido.')
    data = json_request(TOKEN, form=dict(grant_type='authorization_code', client_id=client_id,
                        code=result['code'], code_verifier=verifier, redirect_uri=redirect, resource=RESOURCE))
    try:
        identity = validate_identity(data['id_token'], client_id, nonce)
    except Exception:
        raise ChatGPTError('No se pudo verificar la identidad de ChatGPT.') from None
    if saved and identity['sub'] != saved['subject']:
        raise ChatGPTError('La cuenta seleccionada no coincide con la cuenta guardada.')
    return {'client_id': client_id, 'subject': identity['sub'], 'email': identity.get('email', ''),
            'id_token': data['id_token'], **token_fields(data)}


class ChatGPTSession:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else secure_directory()
        self.path = self.directory / 'accounts.dat'
        self.lock = FileLock(str(self.directory / 'accounts.lock'))
        self.inference_lock = FileLock(str(self.directory / 'inference.lock'))

    def read(self):
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return {'host_id': '', 'active': '', 'accounts': {}}
        if sys.platform == 'win32':
            raw = windows_protect(raw, decrypt=True)
        return json.loads(raw)

    def write(self, data):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        raw = json.dumps(data).encode()
        if sys.platform == 'win32':
            raw = windows_protect(raw)
        fd, tmp = tempfile.mkstemp(dir=self.directory)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def status(self):
        # Only public metadata crosses the webview boundary.
        try:
            data = self.read()
        except (ValueError, OSError, ChatGPTError):
            return {'active': '', 'accounts': [], 'connected': False}
        active = data['accounts'].get(data['active'], {})
        return {'active': data['active'], 'connected': self.authorized(active),
                'paused': bool(active.get('paused')), 'signed_in': bool(active.get('id_token') or active.get('refresh_token')),
                'accounts': [{'id': key, 'label': (a.get('email') or 'ChatGPT') + ' · ' + key[-8:],
                              'connected': self.authorized(a)} for key, a in data['accounts'].items()]}

    @staticmethod
    def authorized(account):
        return DIRECT_SCOPE in account.get('scopes', []) and bool(account.get('access_token') or account.get('refresh_token'))

    def sign_in(self, account_id=''):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.lock.hold():
            data = self.read()
            if not data['host_id']:
                data['host_id'] = 'urn:uuid:' + str(uuid.uuid4())
                self.write(data)
            saved = data['accounts'].get(account_id)
            if account_id and not saved:
                raise ChatGPTError('Cuenta de ChatGPT no encontrada.')
        account = authorization_callback(data['host_id'], saved)
        with self.lock.hold():
            data = self.read()
            previous = data['accounts'].get(account['client_id'], {})
            account['welcome_seen'] = previous.get('welcome_seen', False)
            first_use = self.authorized(account) and not account['welcome_seen']
            account['welcome_seen'] = account['welcome_seen'] or first_use
            data['accounts'][account['client_id']] = account
            data['active'] = account['client_id']
            self.write(data)
        return {**self.status(), 'first_use': first_use}

    def select(self, account_id):
        with self.lock.hold():
            data = self.read()
            if account_id not in data['accounts']:
                raise ChatGPTError('Cuenta de ChatGPT no encontrada.')
            data['active'] = account_id
            self.write(data)
        return self.status()

    def access_token(self, account_id=None):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.lock.hold():
            data = self.read()
            if account_id is not None and account_id != data['active']:
                raise ChatGPTError('La cuenta de ChatGPT ha cambiado. Reintenta el resumen.')
            account = data['accounts'].get(data['active'], {})
            if not self.authorized(account):
                raise ChatGPTError('Conecta una cuenta de ChatGPT y autoriza el uso de su plan.')
            if account.get('access_token') and account.get('expires_at', 0) > time.time() + 90:
                return account['access_token']
            if not account.get('refresh_token'):
                raise ChatGPTError('Vuelve a conectar tu cuenta de ChatGPT.')
            try:
                refreshed = json_request(TOKEN, form=dict(grant_type='refresh_token', client_id=account['client_id'],
                                         refresh_token=account['refresh_token'], resource=RESOURCE))
                account.update(token_fields(refreshed, account))
            except ChatGPTError as exc:
                if exc.code in ('invalid_grant', 'invalid_refresh_token', 'token_expired', 'refresh_token_expired',
                                'refresh_token_invalidated', 'refresh_token_reused'):
                    self.clear_tokens(account)
                    self.write(data)
                raise
            self.write(data)
            if not self.authorized(account):
                raise ChatGPTError('El uso del plan de ChatGPT no está autorizado.')
            return account['access_token']

    @staticmethod
    def clear_tokens(account):
        for key in ('access_token', 'refresh_token', 'id_token', 'expires_at', 'scopes'):
            account.pop(key, None)

    def sign_out(self):
        warning = ''
        with INFERENCE_LOCK, self.inference_lock.hold(), self.lock.hold():
            data = self.read()
            account = data['accounts'].get(data['active'], {})
            if account.get('refresh_token'):
                try:
                    discovery = json_request(ISSUER + '/.well-known/openid-configuration')
                    endpoint = discovery['revocation_endpoint']
                    if parse.urlsplit(endpoint).netloc != 'auth.openai.com' or not endpoint.startswith('https://'):
                        raise ValueError('Invalid revocation endpoint')
                    form = parse.urlencode(dict(token=account['refresh_token'], token_type_hint='refresh_token',
                                                client_id=account['client_id'])).encode()
                    with open_request(request.Request(endpoint, data=form, headers={'Content-Type': 'application/x-www-form-urlencoded'})):
                        pass
                except (ChatGPTError, ValueError, KeyError):
                    warning = 'Sesión eliminada del equipo. No se confirmó la revocación remota; puedes desconectar Estudio en los ajustes de ChatGPT.'
            self.clear_tokens(account)
            self.write(data)
        return {**self.status(), 'warning': warning}

    def resume(self):
        with self.lock.hold():
            data = self.read()
            account = data['accounts'].get(data['active'], {})
            account.pop('paused', None)
            self.write(data)
        return self.status()

    def models(self):
        data = json_request(RESOURCE + '/models', token=self.access_token())
        return [{'id': m['slug'], 'name': m.get('display_name') or m['slug']} for m in data.get('models', [])
                if m.get('visibility') == 'list' and m.get('slug')]

    def infer(self, model, instructions, messages, *, account_id=None):
        body = {'model': model, 'instructions': instructions, 'input': messages, 'store': False, 'stream': True}
        # Serialize inference across the agent and local panel processes.
        with INFERENCE_LOCK, self.inference_lock.hold():
            with self.lock.hold():
                data = self.read()
                selected = account_id if account_id is not None else data['active']
                if data['accounts'].get(selected, {}).get('paused'):
                    raise service_error('subscription_sharing_usage_limit_exceeded', 429)
            req = request.Request(RESOURCE + '/responses', data=json.dumps(body).encode(), headers={
                'Authorization': 'Bearer ' + self.access_token(selected), 'Content-Type': 'application/json', 'Accept': 'text/event-stream'})
            try:
                with open_request(req, timeout=600) as response:
                    return read_stream(response, model)
            except ChatGPTError as exc:
                if exc.status == 429 or exc.code == 'subscription_sharing_usage_limit_exceeded':
                    with self.lock.hold():
                        data = self.read()
                        if selected in data['accounts']:
                            data['accounts'][selected]['paused'] = True
                            self.write(data)
                raise
            except (OSError, ValueError):
                raise ChatGPTError('La respuesta de ChatGPT se interrumpió o no era válida.') from None


def read_stream(response, model):
    text = []
    lines = []
    for raw in response:
        line = raw.decode('utf-8').rstrip('\r\n')
        if line.startswith('data:'):
            lines.append(line[5:].lstrip(' '))
        elif not line and lines:
            data = '\n'.join(lines)
            lines.clear()
            if data == '[DONE]':
                break
            event = json.loads(data)
            kind = event.get('type')
            if kind == 'response.output_text.delta':
                text.append(event.get('delta', ''))
            elif kind in ('response.failed', 'error'):
                info = (event.get('response') or {}).get('error') or event.get('error') or event
                raise service_error(info.get('code', ''))
            elif kind == 'response.incomplete':
                raise ChatGPTError('El resumen de ChatGPT quedó incompleto.')
            elif kind == 'response.completed':
                result = ''.join(text).strip()
                if not result:
                    raise ChatGPTError('ChatGPT no devolvió un resumen.')
                return result, (event.get('response') or {}).get('model') or model
    raise ChatGPTError('La conexión con ChatGPT terminó antes de completar el resumen.')


SESSION = ChatGPTSession()
