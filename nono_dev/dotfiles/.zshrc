# nono-dev zsh configuration

# PATH - ensure common binary locations are available
typeset -U path  # deduplicate
path=(
    $HOME/.local/bin
    $HOME/.cargo/bin
    $HOME/go/bin
    /opt/homebrew/bin
    /opt/homebrew/sbin
    /usr/local/bin
    /usr/local/sbin
    /usr/bin
    /usr/sbin
    /bin
    /sbin
    $path
)
export PATH

# Keep Linux cargo builds on local disk, separate from macOS shared mount.
# Only set inside the VM -- on the macOS host, leave CARGO_TARGET_DIR unset
# so native builds use the default per-project target/ directory.
if [[ "$OSTYPE" == linux* ]]; then
    export CARGO_TARGET_DIR="$HOME/.cargo_target_linux"
fi

# History
HISTFILE=~/.zsh_history
HISTSIZE=100000
SAVEHIST=100000
setopt SHARE_HISTORY
setopt INC_APPEND_HISTORY
setopt EXTENDED_HISTORY
setopt HIST_IGNORE_DUPS
setopt HIST_IGNORE_SPACE
setopt HIST_EXPIRE_DUPS_FIRST

# Directory navigation
setopt AUTO_CD
setopt AUTO_PUSHD
setopt PUSHD_IGNORE_DUPS

# Completion
autoload -Uz compinit && compinit
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}'

# Key bindings
bindkey -e
bindkey '^[[A' history-search-backward
bindkey '^[[B' history-search-forward

# Aliases - use eza if available, fallback to ls
if command -v eza &> /dev/null; then
    alias ls='eza --icons'
    alias ll='eza --icons -alh'
    alias la='eza --icons -a'
    alias lt='eza --icons --tree --level=2'
else
    if [[ "$OSTYPE" == darwin* ]]; then
        alias ls='ls -G'
    else
        alias ls='ls --color=auto'
    fi
    alias ll='ls -alh'
    alias la='ls -A'
fi

# z - directory jumping
if [ -f /opt/homebrew/etc/profile.d/z.sh ]; then
    source /opt/homebrew/etc/profile.d/z.sh
elif [ -f /usr/local/etc/profile.d/z.sh ]; then
    source /usr/local/etc/profile.d/z.sh
elif [ -f /usr/share/z/z.sh ]; then
    source /usr/share/z/z.sh
elif [ -f /usr/local/share/z/z.sh ]; then
    source /usr/local/share/z/z.sh
fi

# zsh-autosuggestions
if [ -f /opt/homebrew/share/zsh-autosuggestions/zsh-autosuggestions.zsh ]; then
    source /opt/homebrew/share/zsh-autosuggestions/zsh-autosuggestions.zsh
elif [ -f /usr/local/share/zsh-autosuggestions/zsh-autosuggestions.zsh ]; then
    source /usr/local/share/zsh-autosuggestions/zsh-autosuggestions.zsh
elif [ -f /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh ]; then
    source /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh
fi

# fzf keybindings (Ctrl-R history, Ctrl-T files, Alt-C cd)
if [ -f /opt/homebrew/opt/fzf/shell/key-bindings.zsh ]; then
    source /opt/homebrew/opt/fzf/shell/key-bindings.zsh
    source /opt/homebrew/opt/fzf/shell/completion.zsh
elif [ -f /usr/local/opt/fzf/shell/key-bindings.zsh ]; then
    source /usr/local/opt/fzf/shell/key-bindings.zsh
    source /usr/local/opt/fzf/shell/completion.zsh
elif [ -f /usr/share/doc/fzf/examples/key-bindings.zsh ]; then
    source /usr/share/doc/fzf/examples/key-bindings.zsh
    source /usr/share/doc/fzf/examples/completion.zsh
fi

#######################################
# General Settings
#######################################

# Modern CLI replacements
if command -v bat &> /dev/null; then
    alias cat='bat -p'
elif command -v batcat &> /dev/null; then
    alias cat='batcat'
fi

if command -v fd &> /dev/null; then
    alias find='fd'
elif command -v fdfind &> /dev/null; then
    alias find='fdfind'
fi

if command -v rg &> /dev/null; then
    alias grep='rg'
else
    alias grep='grep --color=auto'
fi

# Always use modern ls if available
if command -v eza >/dev/null 2>&1; then
  alias ls='eza --icons'
  alias ll='eza -lah --icons'
else
  alias ls='ls --color=auto'
  alias ll='ls -lah'
fi


#######################################
# File & Directory Helpers
#######################################

# Make directory and cd into it
mkcd() {
  mkdir -p -- "$1" && cd -- "$1"
}

# Safer file ops
alias cp='cp -i'
alias mv='mv -i'
alias rm='rm -i'

# Jump to recent dirs
alias j='cd $(fasd -d -e echo | fzf)'

#######################################
# Git Aliases
#######################################

alias gs='git status'
alias ga='git add .'
alias gaa='git add --all'

alias gc='git commit -m'
alias gca='git commit -am'

alias gp='git push'
alias gpl='git pull'

alias gl='git log --oneline --graph --decorate --all'
alias gco='git checkout'
alias gcb='git checkout -b'

# Quick amend
alias gcae='git commit --amend --no-edit'

# Switch to main branch
alias gcm='git checkout main'

# Undo last commit (keep changes)
alias guncommit='git reset --soft HEAD~1'


#######################################
# Network / Debugging
#######################################

# Find process using a port
port() {
  lsof -i tcp:"$1"
}

# Kill process on port
killport() {
  lsof -ti tcp:"$1" | xargs kill -9
}

#######################################
# Rust / Nono Dev
#######################################

# Run nono locally e.g. nn run -- claude
unalias nn 2>/dev/null
nn() {
  cargo run -- "$@"
}

# Install from source (for development)
alias ni='cargo install --path crates/nono-cli'

# nono-dev shortcuts
alias nd='nono-dev'
alias ndf='nono-dev fix'
alias ndt='nono-dev triage'
alias ndr='nono-dev review'
alias ndfeat='nono-dev feature'

# Sandbox management
alias nds='nono-dev sb list'
alias nda='nono-dev sb attach'
alias ndx='nono-dev sb stop'
alias ndi='nono-dev sb inspect'

# Worktree management
alias ndw='nono-dev wt list'
alias ndwc='nono-dev wt cd'
alias ndwx='nono-dev wt cleanup'

# VM management
alias ndvm='nono-dev vm status'
alias ndvc='nono-dev vm connect'

#######################################
# Quality of Life
#######################################

# Exit shortcut
alias x='exit'

# Launch Chrome from CLI
if [[ "$OSTYPE" == darwin* ]]; then
    alias chrome='open -a "Google Chrome"'
else
    alias chrome='google-chrome'
fi

# Clear + list
alias cls='clear && ls'

# Show PATH cleanly
alias path='echo $PATH | tr ":" "\n"'

# Reload shell quickly
alias reload='source ~/.zshrc'


# direnv - auto-load .envrc per directory
if command -v direnv &> /dev/null; then
    eval "$(direnv hook zsh)"
fi

# Starship prompt (must be last hook before local overrides)
if command -v starship &> /dev/null; then
    eval "$(starship init zsh)"
fi

# Local overrides (API keys, secrets, machine-specific config)
[[ -f ~/.zsh_local ]] && source ~/.zsh_local
