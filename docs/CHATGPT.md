# Sign in with ChatGPT

Estudio implements the [official open-source ChatGPT plan usage flow](https://developers.openai.com/siwc/token-sharing-open-source), not an API-key provider, browser automation, session-cookie extraction or undocumented ChatGPT endpoints. Requests use the OAuth bearer token granted by the account owner. Eligibility, usage limits and credits are enforced by OpenAI. The project must satisfy the applicable open-source/locally hosted app requirements before release; the source snapshot did not include a LICENSE file. The maintainer should verify and select the project's license rather than assume that a public repository grants an open-source license.

## Architecture

- `infrastructure/chatgpt.py`: registration, OAuth state/nonce/PKCE, signature and identity verification (PyJWT), protected local credential store, refresh and revocation, per-account model catalog and Responses SSE transport. The loopback server binds to `127.0.0.1`, uses a free port, and closes after success or a three-minute timeout.
- `infrastructure/providers.py`: `ChatGPTProvider` uses the existing summary prompt and schema, validates the completed response and retries invalid JSON once. It does not use or fall back to `OPENAI_API_KEY`.
- `nucleo/config.py`: the `chatgpt` provider is separate from `openai`. The model, account ID and summary-mode selection are persisted in the existing configuration; no OAuth secrets are stored there.
- `asistente/asistente.py` / `asistente.html`: connection, account switching, model picker, revocation and manual resume after reaching plan limits. The webview never receives access, ID or refresh tokens.
- `asistente/class_viewer.py`: a pywebview host for the original `hub/mis-clases.html`. The same web interface runs in local mode, using the existing class service and SQLite task state. It supports the calendar, subject pages, notes, searchable transcripts, task completion, statistics and local summary generation. The Claude artifact keeps its original cloud mode. Remote/multi-device synchronization and a ChatGPT-hosted panel are not included.

## Credentials and limits

The registration file is outside the source tree and class directory: `%LOCALAPPDATA%/estudio/chatgpt/accounts.dat` on Windows (DPAPI current-user encryption), `$XDG_CONFIG_HOME/estudio/chatgpt/accounts.dat` or `~/.config/estudio/chatgpt/accounts.dat` on Linux (owner-only directory/file permissions). The per-installation host identifier is retained across logins. Account registrations remain separate by issued client ID, including those with identical email addresses. Writes are atomic and refreshes are serialized with a file lock. Sign-out attempts remote refresh-token revocation and clears local secrets even if the request fails; remote access can also be revoked in ChatGPT settings. No secrets are put in logs, the repository or the embedded UI.

Class transcript content is sent to OpenAI when a ChatGPT summary is requested; only submit recordings you are authorized to share.

Inference calls `https://api.openai.com/v1/responses` with `store: false`, `stream: true`, and context supplied in each request; it requires `response.completed`. The integration uses no separate API billing route. ChatGPT's plan/credit settings determine actual usage; the user can disable additional credits in [ChatGPT usage settings](https://chatgpt.com/settings/usage). A shared advisory inference lock serializes requests across local processes. On Windows, lock contention can fail after the operating system retry interval; retry the summary later. Sign-out waits for active inference or fails on lock contention. Rate-limit errors pause further inference until the user explicitly resumes. Existing pending/error summaries are retried when saving the summary settings or restarting Estudio. An interrupted or unsuccessful response never replaces the class transcription.

## Tests

Run from the root:

```sh
python -m pip install -r agente/requirements.txt
python tests/test_chatgpt.py
python tests/test_resumen.py
python tests/test_interfaces.py
```

The new offline tests use a real loopback HTTP callback with mocked authorization exchange, a generated RSA key for ID token validation, temporary credential storage, mocked catalog and SSE responses. No real account, network inference, API key or balance is used by these tests.

### Manual acceptance checklist (requires a real eligible account)

- [ ] Start `python agente/app.py --asistente` and choose ChatGPT at the summary step.
- [ ] Complete authorization in the system browser; check the account and model catalog in Estudio. Denied consent must not permit inference.
- [ ] Choose a model, save, record a short permitted test class and stop recording. Verify `estado_resumen=listo`, the actual model and the complete notes in the local viewer.
- [ ] Close/reopen Estudio and verify the account persists. Test refresh with an expired access token and a valid refresh token.
- [ ] Switch accounts/models; confirm the previous account's token is not used. Disconnect and verify that no new summaries are submitted.
- [ ] Verify a rate-limit error pauses jobs; use the usage settings and manual resume when available.
- [ ] Verify original Claude and API-key providers still work and the existing class JSON is preserved.
- [ ] Build/test the Windows installer and Linux AppImage through CI; verify the bundled PyJWT/cryptography dependencies and GUI behavior on both platforms.

## References

- [Registration and sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [Accounts and sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
- [Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [Errors and recovery](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery)
- [Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
