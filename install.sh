#!/usr/bin/env bash
#
# CC CLI Installer
#
# Installs cc into an isolated venv at ~/.cc-cli/venv.
# No system Python pollution. No pyenv required.
#
# Usage:
#   git clone https://github.com/Chrono-Coder/cc.git && cd cc
#   ./install.sh
#
set -euo pipefail

# --- Config ---
CC_HOME="$HOME/.cc-cli"
CC_VENV="$CC_HOME/venv"
MIN_PYTHON="3.10"

# --- Colors ---
R='\033[0m' B='\033[1m' BLUE='\033[0;34m' GREEN='\033[0;32m' RED='\033[0;31m' YELLOW='\033[1;33m'

info()  { echo -e "${BLUE}${B}[cc]${R} $1"; }
ok()    { echo -e "${GREEN}${B}[cc]${R} $1"; }
warn()  { echo -e "${YELLOW}${B}[cc]${R} $1"; }
fail()  { echo -e "${RED}${B}[cc]${R} $1"; exit 1; }

# --- Find Python 3.10+ ---
find_python() {
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            if [ -n "$ver" ] && python3 -c "
import sys
min_parts = [int(x) for x in '$MIN_PYTHON'.split('.')]
cur_parts = [int(x) for x in '$ver'.split('.')]
sys.exit(0 if cur_parts >= min_parts else 1)
" 2>/dev/null; then
                echo "$cmd"
                return
            fi
        fi
    done
}

PYTHON=$(find_python)
if [ -z "$PYTHON" ]; then
    fail "Python $MIN_PYTHON+ is required but not found. Install Python and try again."
fi

PYTHON_VER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
info "Found Python $PYTHON_VER ($PYTHON)"

# --- Verify we're in the cc repo ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -f "$SCRIPT_DIR/pyproject.toml" ]; then
    fail "pyproject.toml not found. Run this script from the cc repo root."
fi

# --- Check for venv module ---
# `import venv` succeeds on Debian/Ubuntu even when venv CREATION will fail:
# the missing piece is ensurepip (shipped in the python3-venv apt package), not
# the venv module itself. Check both so we fail here with a clear fix rather
# than dumping a raw Python traceback at `python -m venv` below.
if ! $PYTHON -c "import venv, ensurepip" 2>/dev/null; then
    PY_MM=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
    fail "Python venv support is incomplete (ensurepip missing). Install it with: sudo apt install python${PY_MM}-venv (Debian/Ubuntu), then re-run ./install.sh"
fi

# --- Clean up old install ---
EXISTING=$(command -v _cc_internal 2>/dev/null || true)
if [ -n "$EXISTING" ] && [[ "$EXISTING" != *".cc-cli"* ]]; then
    warn "Old cc install found at: $EXISTING"
    # Try to uninstall the old pip package
    OLD_PIP=$(dirname "$EXISTING")/pip
    if [ -x "$OLD_PIP" ]; then
        info "Removing old pip install..."
        "$OLD_PIP" uninstall cc-cli -y -q 2>/dev/null && ok "Old pip package removed" || warn "Could not remove old package — remove manually with: pip uninstall cc-cli"
    else
        warn "Remove the old install manually: pip uninstall cc-cli"
    fi
    echo ""
fi

# --- Clean up old .zshrc / .bashrc entries ---
_sed_inplace() {
    local pattern="$1" file="$2"
    # Resolve symlinks — sed -i can't edit through them on macOS
    if [ -L "$file" ]; then
        file="$(readlink "$file" 2>/dev/null || echo "$file")"
        # Handle relative symlinks
        [[ "$file" != /* ]] && file="$(dirname "$2")/$file"
    fi
    if sed --version 2>/dev/null | grep -q GNU; then
        sed -i "$pattern" "$file"
    else
        sed -i '' "$pattern" "$file"
    fi
}

for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
    if [ -f "$rc" ]; then
        CLEANED=false
        if grep -q "# cc status" "$rc" 2>/dev/null; then
            _sed_inplace '/# cc status/d' "$rc"
            CLEANED=true
        fi
        if grep "# cc shell integration" "$rc" 2>/dev/null | grep -qv ".cc-cli/shell"; then
            _sed_inplace '/.cc-cli\/shell/!{/# cc shell integration/d;}' "$rc"
            CLEANED=true
        fi
        if [ "$CLEANED" = true ]; then
            ok "Cleaned stale cc entries from $(basename $rc)"
        fi
    fi
done

# --- Create venv ---
if [ -d "$CC_VENV" ]; then
    info "Existing venv found at $CC_VENV"
    read -p "  Recreate it? [y/N]: " yn
    case "$yn" in
        [Yy]*) rm -rf "$CC_VENV" ;;
        *) info "Keeping existing venv" ;;
    esac
fi

if [ ! -d "$CC_VENV" ]; then
    info "Creating venv at $CC_VENV"
    $PYTHON -m venv "$CC_VENV"
    ok "Venv created"
fi

# --- Install cc-cli ---
info "Installing cc-cli into venv"
"$CC_VENV/bin/pip" install --upgrade pip -q 2>/dev/null
"$CC_VENV/bin/pip" install -e "$SCRIPT_DIR" -q 2>/dev/null

if [ -n "${CC_SYNC:-}" ] || [ "${1:-}" = "--sync" ]; then
    info "Installing sync plugin"
    "$CC_VENV/bin/pip" install -e "$SCRIPT_DIR[sync]" -q 2>/dev/null
fi

ok "cc-cli installed"

# --- Create shell wrapper ---
CC_BIN="$CC_HOME/bin"
mkdir -p "$CC_BIN"

cat > "$CC_BIN/_cc_internal" << 'WRAPPER'
#!/usr/bin/env bash
exec "$HOME/.cc-cli/venv/bin/_cc_internal" "$@"
WRAPPER
chmod +x "$CC_BIN/_cc_internal"

ok "Shell wrapper created at $CC_BIN/_cc_internal"

# --- Detect shell and install integration ---
detect_shell() {
    local parent
    parent=$(ps -p $PPID -o comm= 2>/dev/null | sed 's/^-//')
    case "$parent" in
        zsh|fish|bash) echo "$parent"; return ;;
    esac
    basename "${SHELL:-/bin/bash}"
}

SHELL_NAME=$(detect_shell)
info "Detected shell: $SHELL_NAME"

add_to_path() {
    local rc_file="$1"

    if [ ! -f "$rc_file" ]; then
        mkdir -p "$(dirname "$rc_file")"
        touch "$rc_file"
    fi

    # fish has its own PATH syntax - the bash `export` line only works there
    # by accident of fish's compat shims.
    local path_line='export PATH="$HOME/.cc-cli/bin:$PATH"'
    if [[ "$rc_file" == *"fish"* ]]; then
        path_line='fish_add_path -g "$HOME/.cc-cli/bin"'
    fi
    if ! grep -qF '.cc-cli/bin' "$rc_file"; then
        echo "" >> "$rc_file"
        echo "$path_line" >> "$rc_file"
        ok "Added $CC_BIN to PATH in $rc_file"
    fi
}

case "$SHELL_NAME" in
    zsh)  add_to_path "$HOME/.zshrc" ;;
    bash) add_to_path "$HOME/.bashrc" ;;
    fish) add_to_path "$HOME/.config/fish/config.fish" ;;
    *)    warn "Unsupported shell: $SHELL_NAME. Add $CC_BIN to your PATH manually." ;;
esac

# Regenerate shell integration file (updates hardcoded paths for existing users)
export PATH="$CC_BIN:$PATH"
if [[ "$SHELL_NAME" =~ ^(zsh|bash|fish)$ ]]; then
    info "Installing shell integration for $SHELL_NAME"
    "$CC_VENV/bin/_cc_internal" config shell install --shell "$SHELL_NAME" --force && ok "Shell integration updated" || warn "Shell integration failed - run 'cc config shell install' after setup"
fi

# --- Run setup ---
echo ""
read -p "$(echo -e "${BLUE}${B}[cc]${R} Run initial setup now? [Y/n]: ")" yn
case "$yn" in
    [Nn]*) info "Skipping setup. Run 'cc setup' later to configure." ;;
    *)
        export PATH="$CC_BIN:$PATH"
        "$CC_VENV/bin/_cc_internal" setup
        ;;
esac

# --- Done ---
echo ""
echo -e "${GREEN}${B}======================================${R}"
echo -e "${GREEN}${B}        cc installed successfully      ${R}"
echo -e "${GREEN}${B}======================================${R}"
echo ""
echo "  Restart your terminal, then run: cc"
echo ""
if [ -n "${CC_SYNC:-}" ] || [ "${1:-}" = "--sync" ]; then
    echo "  Sync plugin installed. Configure with:"
    echo "    CC_SERVER=https://your-server CC_API_KEY=your-key"
    echo "    Add to ~/.cc-cli/.env"
    echo ""
fi
