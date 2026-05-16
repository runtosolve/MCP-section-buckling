# MCP for section buckling 

## Getting started

### Claude desktop
1. Go to `Settings` -> `Developer`
2. Click `Edit Config`
3. Open `claude_desktop_config.json`
4. Add the following to `mcpServers`:
```json
{
  "section-buckling": {
    "command": "npx",
    "args": [
        "mcp-remote",
        "https://mcp.runtosolve.com/mcp-section-buckling"
    ]
  }
}
```
5. Save the file and restart Claude desktop.

### Running locally
At step 4, use the following setting instead:
```json
{
  "section-buckling": {
    "command": "npx",
    "args": [
        "mcp-remote",
        "http://127.0.0.1:8000/mcp"
    ]
  }
}
```