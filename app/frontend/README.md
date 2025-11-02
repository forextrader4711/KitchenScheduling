# Kitchen Scheduling Frontend

React + Vite single-page application that provides the planner UI for the kitchen scheduling platform.

## Getting Started

```bash
npm install
npm run dev
```

The development server runs on `http://localhost:5173` and proxies API requests to the FastAPI backend on port `8000`.

## Features

- Monthly planning grid with shift codes and absence indicators.
- Summary panel highlighting worked versus contractual hours.
- Constraint violations panel (placeholder) for rule feedback.
- English/French localization with a simple toggle.
- React Query data layer and Zustand global state.

## Next Steps

- Implement authentication guard and user role routing.
- Wire grid editing interactions (drag/drop, context menu).
- Surface constraint validation results from backend responses.
- Expand localization dictionaries based on UI copy.
