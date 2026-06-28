# Ngrok Setup Instructions

## Prerequisites

1. Install ngrok:
   ```bash
   # For macOS
   brew install ngrok
   # Or download from https://ngrok.com/download
   ```

2. Configure ngrok authentication:
   - Sign up at https://dashboard.ngrok.com/signup
   - Get your authtoken from the dashboard
   - Add it to ngrok config:
   ```bash
   ngrok authtoken YOUR_AUTHTOKEN_HERE
   ```

## Running Your Services

1. Start your Docker containers:
   ```bash
   docker-compose up -d
   ```

2. Activate your backend virtual environment and start the FastAPI server:
   ```bash
   cd backend-ai
   source .venv/bin/activate
   python -m uvicorn src.main:app --port 8001 --reload
   ```

3. Run Celery Worker for ETL Processes (in a new terminal):
   ```bash
   # From backend-ai directory
   cd backend-ai
   source .venv/bin/activate
   celery -A src.celery_app worker --loglevel=info
   ```

4. Expose Services via ngrok:
   ```bash
   ngrok http 8001
   ```

5. This will give you a public URL like `https://xxxxxx.ngrok.io` that forwards to your localhost:8001

## Environment Configuration

To specify allowed origins for your frontend, add this to your backend-ai/.env file:
```
ALLOWED_ORIGINS=https://your-vercel-app.vercel.app,http://localhost:5173
```

## Frontend Deployment

1. Build your frontend:
   ```bash
   cd frontend
   npm run build
   ```

2. Deploy to Vercel:
   ```bash
   # Install Vercel CLI if you haven't
   npm install -g vercel

   # Deploy
   vercel --prod
   ```

## Additional Configuration

The backend is now configured to handle CORS properly for both development and production environments:

1. In development mode, it allows all origins (*)
2. In production mode, it uses the ALLOWED_ORIGINS environment variable

To set specific allowed origins, add to your backend-ai/.env file:
```
ALLOWED_ORIGINS=https://your-vercel-app.vercel.app,https://yourdomain.com
```