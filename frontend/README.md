# OlympusTrail frontend

The React and Leaflet interface is part of OlympusTrail. For local development, install the frontend dependencies and start the planner on port 8000, the guide on port 8001, and Vite with `npm run dev`. Open the Vite address, usually http://localhost:5173; Vite forwards planner and guide requests to their local ports.

The guide calls the planner at `http://localhost:8000` by default. Set `PLANNER_URL` in the guide service environment when the planner has a different origin. In a single origin Vercel deployment, `VERCEL_URL` supplies the deployment origin automatically; set `PLANNER_URL` to that origin if needed. For deployments where the frontend and planner share one origin, configure the guide's `PLANNER_URL` to the site origin.

For complete setup commands, data credits, caveats and validation commands, see the [project README](../README.md).
