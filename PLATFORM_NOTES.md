# 🖥️ Platform-Specific Notes

## Installation Paths

| Platform | Install Directory | CLI Location |
|----------|------------------|--------------|
| **Linux** | `~/.local/share/claude-code-rag` | `~/.local/bin/claude-rag` |
| **macOS** | `~/Library/Application Support/claude-code-rag` | `~/.local/bin/claude-rag` |
| **Windows** | `%LOCALAPPDATA%\claude-code-rag` | `%LOCALAPPDATA%\Programs\claude-code-rag\claude-rag.bat` |

## Prerequisites by Platform

### Linux
```bash
# Debian/Ubuntu
sudo apt update
sudo apt install git python3 python3-venv python3-pip

# Arch/CachyOS
sudo pacman -S git python python-pip

# Fedora
sudo dnf install git python3 python3-pip
```

### macOS
```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install git python@3.11

# Install Ollama
brew install ollama
```

### Windows
- **Git**: Download from [git-scm.com](https://git-scm.com/download/win)
- **Python 3.10+**: Download from [python.org](https://www.python.org/downloads/)
  - ⚠️ Make sure to check "Add Python to PATH" during installation
- **Ollama**: Download from [ollama.ai](https://ollama.ai/download/windows)

## PATH Configuration

### Linux
Add to `~/.bashrc` or `~/.zshrc`:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

Apply changes:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

### macOS
Add to `~/.zshrc` (macOS uses zsh by default):
```bash
export PATH="$HOME/.local/bin:$PATH"
```

Apply changes:
```bash
source ~/.zshrc
```

### Windows
The installer automatically adds the CLI to your PATH. If it doesn't work:

1. Open "Environment Variables" (search in Start menu)
2. Under "User variables", edit "Path"
3. Add: `%LOCALAPPDATA%\Programs\claude-code-rag`
4. Restart your terminal

## MCP Server Configuration

### Linux / macOS
Location: `~/.claude.json`

```json
{
  "mcpServers": {
    "claude-rag": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/claude-code-rag",
        "run",
        "python",
        "mcp_server.py"
      ]
    }
  }
}
```

Replace `/absolute/path/to/claude-code-rag` with:
- Linux: `~/.local/share/claude-code-rag`
- macOS: `~/Library/Application Support/claude-code-rag`

### Windows
Location: `%USERPROFILE%\.claude.json`

```json
{
  "mcpServers": {
    "claude-rag": {
      "command": "python",
      "args": [
        "-m",
        "claude_rag.mcp_server"
      ],
      "env": {
        "PYTHONPATH": "C:\\Users\\YourName\\AppData\\Local\\claude-code-rag"
      }
    }
  }
}
```

Replace `C:\\Users\\YourName` with your actual Windows username.

## Database Location

| Platform | ChromaDB Path |
|----------|---------------|
| **Linux** | `~/.local/share/claude-memory/` |
| **macOS** | `~/Library/Application Support/claude-memory/` |
| **Windows** | `%LOCALAPPDATA%\claude-memory\` |

## Ollama Configuration

### Linux / macOS
Ollama runs as a system service after installation.

Check status:
```bash
ollama list
```

Pull embedding model:
```bash
ollama pull nomic-embed-text
```

### Windows
Ollama runs as a Windows service. It starts automatically with Windows.

Check status (PowerShell):
```powershell
ollama list
```

Pull embedding model:
```powershell
ollama pull nomic-embed-text
```

## Common Issues

### Linux: Command not found
```bash
# Make sure ~/.local/bin is in PATH
echo $PATH | grep ".local/bin"

# If not, add it
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### macOS: Permission denied
```bash
# Fix CLI permissions
chmod +x ~/.local/bin/claude-rag
```

### Windows: Script execution policy
If you get an execution policy error:

```powershell
# Run as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### All Platforms: Ollama connection refused
```bash
# Check if Ollama is running
curl http://localhost:11434

# If not running:
# Linux/macOS: systemctl start ollama  OR  brew services start ollama
# Windows: Start Ollama from Start menu
```

## Shell Integration

### Fish (Linux/macOS)
If you use Fish shell, add to `~/.config/fish/config.fish`:
```fish
set -gx PATH $HOME/.local/bin $PATH
```

### PowerShell (Windows)
Edit your PowerShell profile (`notepad $PROFILE`):
```powershell
$env:Path += ";$env:LOCALAPPDATA\Programs\claude-code-rag"
```

## Virtual Environment Activation

### Linux / macOS
```bash
source ~/.local/share/claude-code-rag/.venv/bin/activate
# or on macOS:
source "~/Library/Application Support/claude-code-rag/.venv/bin/activate"
```

### Windows (PowerShell)
```powershell
& "$env:LOCALAPPDATA\claude-code-rag\.venv\Scripts\Activate.ps1"
```

### Windows (CMD)
```cmd
%LOCALAPPDATA%\claude-code-rag\.venv\Scripts\activate.bat
```
