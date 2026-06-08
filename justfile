# List all just commands
default:
    just --list

# Open the tmux stack(lazyvim, opencode, lazygit, and etc.)
tmux:
    tmuxp load tmuxp.yaml
