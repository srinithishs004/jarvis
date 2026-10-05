# JARVIS Windows Agent

Minimal Windows device agent for JARVIS OS.

## Current capability

The agent currently supports only:

- `windows.system.info`

The agent rejects unknown tool names and does not provide arbitrary
shell, PowerShell, keyboard, mouse, filesystem, or process execution.

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
