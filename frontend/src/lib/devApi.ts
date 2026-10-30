/** Local FastAPI port (8010 avoids common 8000 conflicts e.g. other local tools). */
export const DEV_API_PORT = 8010;

export const DEV_API_ORIGIN = `http://127.0.0.1:${DEV_API_PORT}`;
