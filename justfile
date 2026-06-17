# List all just commands
default:
    just --list

# Open the tmux stack(lazyvim, opencode, lazygit, and etc.)
tmux:
    tmuxp load tmuxp.yaml

# Build the docker image
build:
    docker compose build

# Run the Django app and dependecies services in development mode
up:
    docker compose up -d

# Stop all the containers
down:
    docker compose down

# Enter in the container shell
shell:
    docker compose run --rm web sh

# Run manage.py inside the container
mng +command:
    docker compose run --rm web uv run python manage.py {{ command }}
