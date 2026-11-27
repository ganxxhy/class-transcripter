"""Offline regression tests for the ChatGPT subscription provider."""
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib import parse, request
from unittest.mock import patch

os.environ['AGENTE_CLASES_DATOS'] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agente'))
from infrastructure import chatgpt
from infrastructure.providers import ChatGPTProvider, elegir_proveedor
from nucleo import config


VALID = {'titulo': 'T', 'resumen': '## Tema\nTexto', 'puntos_clave': [], 'conceptos': [],
         'destacados': [], 'tareas': [], 'calidad_audio': 'buena'}


def sse(*events):
    return io.BytesIO(''.join('data: ' + json.dumps(event) + '\n\n' for event in events).encode())


def tokens(**updates):
    return {'access_token': 'access-test', 'refresh_token': 'refresh-test', 'token_type': 'Bearer',
            'scope': chatgpt.SCOPES, 'expires_in': 3600, **updates}


class ChatGPTTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.session = chatgpt.ChatGPTSession(self.temp.name)
        self.account = {'client_id': 'oaiapp_test', 'subject': 'sub-test', 'email': 'test@example.invalid',
                        'id_token': 'id-test', **chatgpt.token_fields(tokens())}
        self.session.write({'host_id': 'urn:uuid:test', 'active': self.account['client_id'],
                            'accounts': {self.account['client_id']: self.account}})

    def test_registration_callback_pkce_and_granted_scope(self):
        captured = {}

        def browser(url):
            query = {k: v[0] for k, v in parse.parse_qs(parse.urlsplit(url).query).items()}
            captured.update(query)
            def callback():
                # Wrong state must not consume the pending attempt.
                try:
                    request.urlopen(query['redirect_uri'] + '?code=bad&state=bad', timeout=5)
                except Exception:
                    pass
                with request.urlopen(query['redirect_uri'] + '?' + parse.urlencode(
                        {'state': query['state'], 'code': 'code-test', 'client_id': 'oaiapp_new'}), timeout=5):
                    pass
            threading.Thread(target=callback, daemon=True).start()
            return True

        with patch.object(chatgpt.webbrowser, 'open', side_effect=browser), \
             patch.object(chatgpt, 'json_request', return_value=tokens(id_token='id')) as exchange, \
             patch.object(chatgpt, 'validate_identity', return_value={'sub': 'new-sub', 'email': 'new@example.invalid'}) as identity:
            record = chatgpt.authorization_callback('urn:uuid:test')
        self.assertEqual(captured['client_id'], 'dynamic_agent_client')
        self.assertEqual(captured['agent_name_hint'], 'Estudio')
        self.assertEqual(captured['ext_agent_host_id'], 'urn:uuid:test')
        self.assertEqual(captured['scope'], chatgpt.SCOPES)
        self.assertTrue(captured['redirect_uri'].startswith('http://127.0.0.1:'))
        form = exchange.call_args.kwargs['form']
        self.assertEqual(form['client_id'], 'oaiapp_new')
        self.assertEqual(form['redirect_uri'], captured['redirect_uri'])
        import hashlib, base64
        expected = base64.urlsafe_b64encode(hashlib.sha256(form['code_verifier'].encode()).digest()).decode().rstrip('=')
        self.assertEqual(captured['code_challenge'], expected)
        identity.assert_called_once_with('id', 'oaiapp_new', captured['nonce'])
        self.assertTrue(self.session.authorized(record))

    def test_identity_verifies_signature_audience_and_nonce(self):
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        claims = {'sub': 'sub', 'iss': chatgpt.ISSUER, 'aud': 'oaiapp_test', 'nonce': 'nonce', 'exp': time.time() + 300}
        token = jwt.encode(claims, key, algorithm='RS256', headers={'kid': 'test'})
        with patch.object(jwt.PyJWKClient, 'get_signing_key_from_jwt') as jwk:
            jwk.return_value.key = key.public_key()
            self.assertEqual(chatgpt.validate_identity(token, 'oaiapp_test', 'nonce')['sub'], 'sub')
            with self.assertRaises(jwt.InvalidAudienceError):
                chatgpt.validate_identity(token, 'oaiapp_other', 'nonce')
            with self.assertRaises(chatgpt.ChatGPTError):
                chatgpt.validate_identity(token, 'oaiapp_test', 'wrong')

    def test_no_scope_no_inference(self):
        data = self.session.read()
        data['accounts']['oaiapp_test']['scopes'] = ['openid']
        self.session.write(data)
        self.assertFalse(self.session.status()['connected'])
        with patch.object(chatgpt, 'open_request') as network, self.assertRaises(chatgpt.ChatGPTError):
            self.session.infer('model', 'instructions', [])
        network.assert_not_called()

    def test_public_status_and_account_switch(self):
        self.assertNotIn('access-test', json.dumps(self.session.status()))
        if os.name != 'nt':
            self.assertEqual(self.session.path.stat().st_mode & 0o777, 0o600)
        with patch.object(chatgpt, 'authorization_callback', return_value={**self.account, 'client_id': 'oaiapp_other'}):
            self.session.sign_in()
        self.assertEqual(len(self.session.status()['accounts']), 2)
        with self.assertRaises(chatgpt.ChatGPTError):
            self.session.access_token('oaiapp_test')
        self.session.select('oaiapp_test')
        self.assertEqual(self.session.access_token('oaiapp_test'), 'access-test')

    def expire(self):
        data = self.session.read()
        data['accounts']['oaiapp_test']['expires_at'] = 0
        self.session.write(data)

    def test_refresh_rotates_credentials(self):
        self.expire()
        with patch.object(chatgpt, 'json_request', return_value=tokens(access_token='new-access', refresh_token='new-refresh')) as exchange:
            self.assertEqual(self.session.access_token(), 'new-access')
            self.assertEqual(self.session.access_token(), 'new-access')
        self.assertEqual(exchange.call_count, 1)
        self.assertEqual(exchange.call_args.kwargs['form']['client_id'], 'oaiapp_test')
        self.assertEqual(self.session.read()['accounts']['oaiapp_test']['refresh_token'], 'new-refresh')

    def test_revoked_refresh_clears_tokens_not_registration(self):
        self.expire()
        with patch.object(chatgpt, 'json_request', side_effect=chatgpt.service_error('invalid_grant', 400)):
            with self.assertRaises(chatgpt.ChatGPTError):
                self.session.access_token()
        self.assertFalse(self.session.status()['connected'])
        self.assertEqual(self.session.status()['active'], 'oaiapp_test')

    def test_model_catalog_filters_visibility(self):
        with patch.object(chatgpt, 'json_request', return_value={'models': [
                {'slug': 'shown', 'display_name': 'Shown', 'visibility': 'list'}, {'slug': 'hidden', 'visibility': 'hidden'}]}) as call:
            self.assertEqual(self.session.models(), [{'id': 'shown', 'name': 'Shown'}])
        self.assertEqual(call.call_args.args[0], chatgpt.RESOURCE + '/models')
        self.assertEqual(call.call_args.kwargs['token'], 'access-test')

    def test_stream_and_public_endpoint(self):
        stream = sse({'type': 'response.output_text.delta', 'delta': 'abc'},
                     {'type': 'response.output_text.delta', 'delta': 'def'},
                     {'type': 'response.completed', 'response': {'model': 'actual'}})
        with patch.object(chatgpt, 'open_request', return_value=stream) as call:
            self.assertEqual(self.session.infer('model', 'instructions', [{'role': 'user', 'content': 'class'}]), ('abcdef', 'actual'))
        req = call.call_args.args[0]
        self.assertEqual(req.full_url, chatgpt.RESOURCE + '/responses')
        self.assertEqual(req.get_header('Authorization'), 'Bearer access-test')
        self.assertEqual(json.loads(req.data), {'model': 'model', 'instructions': 'instructions',
                         'input': [{'role': 'user', 'content': 'class'}], 'store': False, 'stream': True})

    def test_incomplete_stream_is_not_success(self):
        for stream in (sse({'type': 'response.output_text.delta', 'delta': 'partial'}), sse({'type': 'response.incomplete'})):
            with self.assertRaises(chatgpt.ChatGPTError):
                chatgpt.read_stream(stream, 'model')

    def test_limit_pauses_requests_until_resumed(self):
        stream = sse({'type': 'response.failed', 'response': {'error': {'code': 'subscription_sharing_usage_limit_exceeded'}}})
        with patch.object(chatgpt, 'open_request', return_value=stream) as call:
            with self.assertRaises(chatgpt.ChatGPTError):
                self.session.infer('model', 'instructions', [])
            self.assertTrue(self.session.status()['paused'])
            with self.assertRaises(chatgpt.ChatGPTError):
                self.session.infer('model', 'instructions', [])
            self.assertEqual(call.call_count, 1)
        self.session.resume()
        self.assertFalse(self.session.status()['paused'])

    def test_signout_clears_credentials_and_keeps_mapping(self):
        with patch.object(chatgpt, 'json_request', return_value={'revocation_endpoint': chatgpt.ISSUER + '/revoke'}), \
             patch.object(chatgpt, 'open_request', return_value=io.BytesIO()) as revoke:
            status = self.session.sign_out()
        self.assertFalse(status['connected'])
        self.assertEqual(status['active'], 'oaiapp_test')
        self.assertNotIn('refresh_token', self.session.read()['accounts']['oaiapp_test'])
        self.assertIn(b'token=refresh-test', revoke.call_args.args[0].data)

    def test_provider_reuses_summary_schema_and_never_uses_api_key(self):
        cfg = config.vacia()
        cfg['ajustes'].update(proveedor='chatgpt', modelo_chatgpt='model', chatgpt_account_id='oaiapp_test', openai_api_key='do-not-use')
        self.assertEqual(config.api_key(cfg), '')
        self.assertTrue(config.resumen_en_pc(cfg))
        provider = elegir_proveedor(cfg)
        self.assertIsInstance(provider, ChatGPTProvider)
        with patch.object(chatgpt, 'SESSION', self.session), patch.object(self.session, 'infer', side_effect=[('{}', 'm'), (json.dumps(VALID), 'm')]) as infer:
            result, model = provider.generar(cfg, '', 'class transcript')
        self.assertEqual(result['titulo'], 'T')
        self.assertEqual(model, 'm')
        self.assertEqual(infer.call_count, 2)
        self.assertEqual(infer.call_args.kwargs['account_id'], 'oaiapp_test')


if __name__ == '__main__':
    unittest.main()
