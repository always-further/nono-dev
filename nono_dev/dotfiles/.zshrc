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

# History
HISTFILE=~/.zsh_history
HISTSIZE=10000
SAVEHIST=10000
setopt SHARE_HISTORY
setopt HIST_IGNORE_DUPS
setopt HIST_IGNORE_SPACE

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
alias grep='grep --color=auto'
alias gs='git status'
alias gd='git diff'
alias gl='git log --oneline --graph'

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

# Starship prompt
if command -v starship &> /dev/null; then
    eval "$(starship init zsh)"
fi
