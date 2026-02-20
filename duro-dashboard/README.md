# Duro Dashboard

Real-time web dashboard for the Duro memory system with an industrial/terminal design aesthetic.

## Architecture

```
React App (5173)  <--HTTP/SSE-->  FastAPI (8001)  <--SQLite-->  ~/.duro/
```

## Quick Start

### Backend

```bash
cd api
python -m venv venv
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

### Frontend

```bash
cd client
npm install
npm run dev
```

Dashboard accessible at `http://localhost:5173`

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Server health + latency |
| `GET /api/stats` | Artifact counts by type |
| `GET /api/artifacts` | List artifacts (paginated) |
| `GET /api/artifacts/:id` | Single artifact detail |
| `GET /api/stream/heartbeat` | SSE: health pulse every 5s |
| `GET /api/stream/activity` | SSE: new artifact events |

## Tech Stack

- **Frontend**: Vite + React 18 + TypeScript + Tailwind CSS
- **Backend**: FastAPI + sse-starlette
- **State**: React Query
- **Data**: SQLite (`~/.agent/memory/index.db`)

## Features

- Real-time heartbeat indicator
- Live activity feed via SSE
- Memory browser with type filtering
- Stats grid showing artifact counts
- Industrial terminal aesthetic
