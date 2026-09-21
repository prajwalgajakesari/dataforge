# DataForge web prototype

A React 19 + Vite 7 prototype of a visual modeling UI. It walks through three steps
(pick a source, pick a strategy, open the canvas) and renders tables on a React Flow
canvas (`@xyflow/react`) with a chat sidebar.

It is not connected to the API yet. `src/App.tsx` carries a `TODO` where the backend
session would be created, and no component calls `http://localhost:8000`.

```bash
cd web
npm install
npm run dev      # http://localhost:5173
npm run build
npm run lint
```

The backend it is meant to talk to is the FastAPI server in `../api` (start it with
`uv run uvicorn api.server:app --reload` from the repository root).
