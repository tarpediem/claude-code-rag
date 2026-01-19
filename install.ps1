# Claude Code RAG - Windows installer
# Usage: iwr -useb https://raw.githubusercontent.com/tarpediem/claude-code-rag/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

Write-Host "🧠 Installing Claude Code RAG..." -ForegroundColor Cyan

# Check for required tools
if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Error: git is required but not installed." -ForegroundColor Red
    Write-Host "   Install from: https://git-scm.com/download/win" -ForegroundColor Yellow
    exit 1
}

if (!(Get-Command python -ErrorAction SilentlyContinue) -and !(Get-Command python3 -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Error: Python 3.10+ is required but not installed." -ForegroundColor Red
    Write-Host "   Install from: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Use python or python3
$PYTHON_CMD = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "python3" }

# Install directory
$INSTALL_DIR = Join-Path $env:LOCALAPPDATA "claude-code-rag"
$BIN_DIR = Join-Path $env:LOCALAPPDATA "Programs\claude-code-rag"

# Clone repository
if (Test-Path $INSTALL_DIR) {
    Write-Host "📦 Updating existing installation..." -ForegroundColor Green
    Set-Location $INSTALL_DIR
    git pull
} else {
    Write-Host "📦 Cloning repository..." -ForegroundColor Green
    New-Item -ItemType Directory -Force -Path (Split-Path $INSTALL_DIR) | Out-Null
    git clone https://github.com/tarpediem/claude-code-rag.git $INSTALL_DIR
    Set-Location $INSTALL_DIR
}

# Install with pip (uv detection for Windows)
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "📦 Installing with uv..." -ForegroundColor Green
    uv sync
} else {
    Write-Host "📦 Installing with pip..." -ForegroundColor Green
    & $PYTHON_CMD -m venv .venv

    # Activate venv
    $ACTIVATE_SCRIPT = Join-Path $INSTALL_DIR ".venv\Scripts\Activate.ps1"
    if (Test-Path $ACTIVATE_SCRIPT) {
        & $ACTIVATE_SCRIPT
    } else {
        Write-Host "❌ Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }

    & python -m pip install --upgrade pip
    & pip install -e .
}

# Create CLI launcher
New-Item -ItemType Directory -Force -Path $BIN_DIR | Out-Null

# Create batch wrapper
$BATCH_WRAPPER = @"
@echo off
set RAG_DIR=$INSTALL_DIR
"%RAG_DIR%\.venv\Scripts\python.exe" -m claude_rag %*
"@
$BATCH_PATH = Join-Path $BIN_DIR "claude-rag.bat"
$BATCH_WRAPPER | Out-File -FilePath $BATCH_PATH -Encoding ASCII

# Create PowerShell wrapper
$PS_WRAPPER = @"
`$RAG_DIR = "$INSTALL_DIR"
& "`$RAG_DIR\.venv\Scripts\python.exe" -m claude_rag `$args
"@
$PS_PATH = Join-Path $BIN_DIR "claude-rag.ps1"
$PS_WRAPPER | Out-File -FilePath $PS_PATH -Encoding UTF8

Write-Host "✅ CLI installed at $BIN_DIR" -ForegroundColor Green

# Check PATH
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BIN_DIR*") {
    Write-Host "⚠️  Adding $BIN_DIR to PATH..." -ForegroundColor Yellow
    [Environment]::SetEnvironmentVariable(
        "Path",
        "$UserPath;$BIN_DIR",
        "User"
    )
    $env:Path = "$env:Path;$BIN_DIR"
    Write-Host "✅ PATH updated. Restart your terminal to apply changes." -ForegroundColor Green
}

# Check for Ollama
if (!(Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "⚠️  Ollama not found." -ForegroundColor Yellow
    Write-Host "   Install from: https://ollama.ai/download/windows" -ForegroundColor Yellow
    Write-Host "   After installing, run: ollama pull nomic-embed-text" -ForegroundColor Yellow
} else {
    Write-Host "🤖 Pulling embedding model..." -ForegroundColor Green
    try {
        ollama pull nomic-embed-text
    } catch {
        Write-Host "⚠️  Failed to pull model, run manually: ollama pull nomic-embed-text" -ForegroundColor Yellow
    }
}

# MCP server config
$CLAUDE_JSON = Join-Path $env:USERPROFILE ".claude.json"
if (Test-Path $CLAUDE_JSON) {
    Write-Host ""
    Write-Host "🔌 Found .claude.json - Add this MCP server config:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host '  "claude-rag": {'
    Write-Host '    "command": "python",'
    Write-Host '    "args": ['
    Write-Host "      `"-m`", `"claude_rag.mcp_server`""
    Write-Host '    ],'
    Write-Host "    `"env`": {"
    Write-Host "      `"PYTHONPATH`": `"$INSTALL_DIR`""
    Write-Host "    }"
    Write-Host '  }'
    Write-Host ""
}

# Initialize database
Write-Host "🗄️  Initializing database..." -ForegroundColor Green
try {
    & "$INSTALL_DIR\.venv\Scripts\python.exe" -m claude_rag init
} catch {
    Write-Host "⚠️  Database initialization failed (may be normal)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Usage:" -ForegroundColor Cyan
Write-Host "  claude-rag index C:\your\docs       # Index files"
Write-Host "  claude-rag search `"your query`"      # Search memories"
Write-Host "  claude-rag web                       # Launch Web UI"
Write-Host "  claude-rag ui                        # Launch TUI"
Write-Host ""
Write-Host "📖 Documentation: https://github.com/tarpediem/claude-code-rag" -ForegroundColor Cyan
