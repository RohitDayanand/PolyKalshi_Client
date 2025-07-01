SETUP.README

After setting up the environment variables (Kalshi key text file titled kalshi_key_file.txt, API code in the global env), you can run the environment

1. Install the backend depndencies using poetry install. Highly recommend creating a virtual environment first. Then go cd backend/ and run uvicorn main:app --reload. The backend server is now ready and awaiting a frontend connection
We will be running the backend using uvicorn and FastAPI, which helps us bypass browser CORs for Kalshi's websocket connections and build in server-side throttling to keep the frontend performant
2. Install the frontend by first doing cd frontend/ and then pnpm install, then pnpm run to get the frontend working. Click the link. Y
3. Done

In rare cases where ports are already being used, it's possible that you will have to configure the ports in uvicorn and the frontend to align as the frontend believes the backend is accessible on port 8000



