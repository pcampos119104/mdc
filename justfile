# List all just commands
default:
    just --list

# Open the Herdr development workspace
workspace:
    herdr

# Build the docker image
build:
    docker compose build

# Run the Django app and dependecies services in development mode
up:
    docker compose up -d

# Stop all the containers
down:
    docker compose down

# Wait until the database is ready to receive connections
wait-db:
    docker compose exec -T db sh -c 'until pg_isready; do sleep 1; done'

# Enter in the container shell
shell:
    docker compose run --rm web sh

# Run manage.py inside the container
mng +command:
    docker compose run --rm web uv run python manage.py {{ command }}

# Run tests inside the web container
test:
    docker compose run --rm web uv run pytest

# Build the production Docker image locally
prod-build:
    docker build -f web/Dockerfile -t mdc-web:prod web
