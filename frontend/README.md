# Frontend Shell

Minimal React + Vite dashboard shell for the AOC POC.

## Run

```powershell
uvicorn backend.api:app --reload --port 8000
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

## Build

```powershell
cd frontend
npm run build
```

## Preview

```powershell
cd frontend
npm run preview
```

Notes:
- This shell uses static mock data only.
- It expects the backend API at `http://localhost:8000`.
