# JARVIS Windows Agent

Minimal Windows device agent for JARVIS OS.

## Current capabilities

The agent supports these explicitly allowlisted tools:

- `windows.system.info` — read basic Windows system information
- `windows.app.list` — list visible top-level application windows
- `windows.app.launch` — launch an explicitly allowlisted application
- `windows.app.close` — request that a specific window close
- `windows.window.focus` — focus a specific window

The agent rejects unknown tool names.

Application launching uses an explicit application allowlist and does not
invoke a shell, PowerShell, or arbitrary command execution.

The agent does not provide arbitrary shell, PowerShell, keyboard, mouse,
filesystem, or unrestricted process execution.

## Configuration

Set these environment variables:

- `JARVIS_SERVER_URL`
- `JARVIS_DEVICE_ID`
- `JARVIS_DEVICE_NAME`
- `JARVIS_DEVICE_AUTH_SECRET`

The authentication secret must match the JARVIS server's
`JARVIS_DEVICE_AUTH_SECRET`.

## Run

From this directory:

```powershell
python -m pip install -r requirements.txt

$env:JARVIS_SERVER_URL="wss://your-server/ws/devices"
$env:JARVIS_DEVICE_ID="windows-01"
$env:JARVIS_DEVICE_NAME="My Windows PC"
$env:JARVIS_DEVICE_AUTH_SECRET="your-secret"

python -m jarvis_agent
