# JARVIS Windows Agent

Minimal Windows device agent for JARVIS OS.

## Current capabilities

The agent supports these explicitly allowlisted tools:

- `windows.system.info` — read basic Windows system information
- `windows.app.list` — list visible top-level application windows
- `windows.app.launch` — launch an explicitly allowlisted application
- `windows.app.close` — request that a specific window close
- `windows.window.focus` — focus a specific window
- `windows.keyboard.type` — type text through the Windows input layer
- `windows.keyboard.press` — press an explicitly allowlisted key
- `windows.mouse.move` — move the mouse cursor
- `windows.mouse.click` — click an explicitly allowlisted mouse button
- `windows.clipboard.read` — read text from the Windows clipboard
- `windows.clipboard.write` — write text to the Windows clipboard
- `windows.filesystem.read` — read a UTF-8 text file within the configured filesystem root
- `windows.filesystem.list` — list entries within the configured filesystem root
- `windows.filesystem.write` — write a UTF-8 text file within the configured filesystem root

The agent rejects unknown tool names and only executes tools from its explicit
allowlist.

Application launching uses an explicit application allowlist and does not
invoke a shell, PowerShell, or arbitrary command execution.

Keyboard input uses an explicit key allowlist. Mouse input uses explicit
coordinate and button validation. Clipboard controls are text-only.
Filesystem controls are restricted to the configured filesystem root and
reject absolute paths, parent traversal,
symlinks, and junctions.

The agent does not provide arbitrary shell, PowerShell, or unrestricted
process execution.

## Configuration

Set these environment variables:

- `JARVIS_SERVER_URL`
- `JARVIS_DEVICE_ID`
- `JARVIS_DEVICE_NAME`
- `JARVIS_DEVICE_AUTH_SECRET`
- `JARVIS_FILESYSTEM_ROOT`

The authentication secret must match the JARVIS server's
`JARVIS_DEVICE_AUTH_SECRET`.

`JARVIS_FILESYSTEM_ROOT` must point to an existing directory. Filesystem
operations are confined to this directory.

## Run

From this directory:

```powershell
python -m pip install -r requirements.txt

$env:JARVIS_SERVER_URL="wss://your-server/ws/devices"
$env:JARVIS_DEVICE_ID="windows-01"
$env:JARVIS_DEVICE_NAME="My Windows PC"
$env:JARVIS_DEVICE_AUTH_SECRET="your-secret"
$env:JARVIS_FILESYSTEM_ROOT="C:\\Users\\MyUser\\Documents"

python -m jarvis_agent
