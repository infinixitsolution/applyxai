# Release version (Desktop + agent worker)

Bump **one line** in the repo root [`VERSION`](../VERSION) file (semver, e.g. `1.2.1`).

Then run:

```powershell
.\scripts\build_desktop.ps1
```

The script will:

- Sync `desktop/package.json`, `desktop/src/productVersion.ts`, and PyInstaller output name
- Produce `dist/agent-worker-v<VERSION>.exe` and copy to `dist/agent-worker.exe`
- Produce `dist/ApplyXAI-Desktop-Setup-v<VERSION>.exe` and copy to `dist/ApplyXAI-Desktop-Setup.exe`

Python reads the same version via `agent.version.AGENT_VERSION` (bundled `VERSION` in the worker exe).
