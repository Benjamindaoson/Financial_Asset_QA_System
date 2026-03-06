# Frontend Notes

This frontend is a React 18 + Vite interface for the Financial Asset QA System.

## What it renders

- chat input and streaming answer output
- tool execution states
- stock cards for price, change, and profile tools
- chart rendering for historical price data
- quick-question shortcuts

## Important behavior

- the sidebar does not show fake real-time prices anymore
- verified tool results are rendered inside the chat flow
- streaming messages are finalized through a ref-backed draft to avoid stale React state

## Local run

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:5173`

## Backend dependency

The frontend expects the backend API to be reachable at `/api`. During local development, use the Vite proxy defined in `vite.config.ts` or serve frontend and backend from the same host setup.

## Current gaps

- bundle size still needs code splitting
- several legacy components still contain old copy and should be normalized
