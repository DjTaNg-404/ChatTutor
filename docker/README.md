# Docker Deployment

## Files

- `docker/Dockerfile`
- `docker/Dockerfile.frontend`
- `docker/docker-compose.yml`
- `docker/nginx.frontend.conf`
- `docker/requirements.txt`

## Start

Run from the repository root:

```powershell
Copy-Item .env.example .env
```

Then fill in your real API keys in `.env`, and start:

```powershell
docker compose -f docker/docker-compose.yml up --build -d
```

## Stop

```powershell
docker compose -f docker/docker-compose.yml down
```

## Check

```powershell
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs -f backend
```

## Endpoints

- API root: `http://localhost:8000/`
- Swagger: `http://localhost:8000/docs`
- Frontend: `http://localhost:8080/`

## Notes

- Runtime data is stored in `./memory`.
- Knowledge graph output is stored in `./kg_output`.
- HuggingFace cache is stored in the Docker volume `hf-cache`.
- This Docker profile is intentionally slimmed down for the chat backend.
- `RAG_ENABLED=false`, so semantic vector retrieval is disabled and the service falls back to the lightweight retrieval path.
- `KG_ENABLED=false`, so knowledge graph routes are not registered in this container.
- The desktop pet is not included in this Docker setup.
