# Cherry AI — VOSI Execution Agent integration

This branch adds the backend integration seam while preserving the existing screen assistant.

## Install the agent package

1. Copy the supplied `vosi_agent_ready.zip` into this `backend/` directory.
2. From `backend/`, run `python install_execution_agent.py`.
3. Install backend dependencies: `python -m pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and set `VOSI_API_TOKEN` to a long random secret. Never commit `.env`.
5. Start the backend using the existing project command.
6. Check `GET http://127.0.0.1:8001/execution-agent/status`. It must report `available: true`.

The router uses `x-vosi-token` for protected HTTP requests and token authentication for its WebSocket clients. The example autonomy profile is `approval`; do not switch to trusted mode until permissions have been reviewed.

## Cherry AI execution API

Once the package is installed, the VOSI router exposes its documented endpoints:
- `POST /agent/run`
- `GET /agent/{task_id}`
- `GET /agent/{task_id}/live`
- `POST /agent/{task_id}/confirm`
- `POST /agent/{task_id}/answer`
- `POST /agent/{task_id}/cancel`
- `POST /agent/{task_id}/pause` and `/resume`
- `WS /device/{device_id}` and `WS /browser/{browser_id}`

The existing Cherry AI chat/voice client is not yet wired to call these routes. This branch deliberately keeps the current chat path intact until the agent package is installed and smoke-tested. Do not treat a loaded router as proof that a physical device or browser client is connected.
