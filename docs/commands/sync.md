# cc sync

Synchronize cc data across multiple machines through a central server. Requires the sync plugin: `cc sync enable`.

## Install

```bash
cc sync enable
```

This installs the `pycryptodomex` dependency into cc's venv. Restart your terminal after enabling.

## Setup

1. **Start a sync server** on your central machine:
   ```bash
   python -m cc.sync.http_server --port 9100
   ```

2. **Register each device** — run this **on the server**, since it writes the
   key into the server's own database:
   ```bash
   cc sync register --name laptop
   ```
   Running `cc sync register` on a *client* only creates a key locally; the
   server will never recognize it.

3. **Configure each client** with `cc sync setup` (interactive):
   ```bash
   cc sync setup
   ```
   It prompts for the server URL + API key, verifies them against the server,
   and writes `~/.cc-cli/.env` (permissions `600`). Refuses to save a key the
   server rejects, so you find out immediately instead of on first push.

   To configure by hand instead, write `~/.cc-cli/.env` yourself:
   ```
   CC_SERVER=https://cc-sync.your-domain.org
   CC_API_KEY=<key from step 2>
   ```

4. **Restart the daemon**: `cc daemon restart` — auto-sync starts immediately.

5. **First sync on a new device**: `cc sync resolve` to fix paths.

## Commands

| Command | Description |
|---------|-------------|
| `cc sync` | Show sync status (pending counts + server connection) |
| `cc sync enable` | Install the sync plugin |
| `cc sync setup` | Configure + verify this device's server URL and API key, write `~/.cc-cli/.env` |
| `cc sync push` | Push local data to the server |
| `cc sync pull` | Pull data from the server |
| `cc sync stamp` | Assign sync IDs to unstamped rows |
| `cc sync resolve` | Remap versions and paths after pulling to a new device |
| `cc sync register --name NAME` | Register a device and get an API key (run on server) |
| `cc sync server` | Start the sync HTTP server |

## Options

| Option | Description |
|--------|-------------|
| `--name` | Device name for register, or project name for link |
| `--since` | ISO timestamp for pull (only pull changes after this time) |
| `--port` | Port for sync server (default: 9100) |

## Synced tables

version, setting, database, project, environment, switch_log, backup, repository, skill_tag, knowledge_index

Sensitive settings (`github_pat`, sync credentials) are never synced.

## Encryption

All sync payloads are encrypted with AES-256-GCM. The encryption key is derived from the device's API key — no extra configuration needed.

## Auto-sync

When `CC_SERVER` and `CC_API_KEY` are configured, the daemon runs a background push/pull cycle every 5 minutes.
