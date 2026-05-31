# Deployment Guide

## Render.com Setup

### 1. Push to GitHub
```bash
git add .
git commit -m "Add FastAPI backend"
git push
```

### 2. Create Web Service on Render
1. Go to https://render.com
2. Click **New +** → **Web Service**
3. Connect your GitHub repository
4. Configure:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 3. Environment Variables
Add these in Render dashboard:
```
ELASTICSEARCH_URL=https://...
ELASTICSEARCH_API_KEY=...
OPENAI_API_KEY=sk-...
```

### 4. Deploy
Click **Deploy**. First deployment takes ~5 minutes (PyTorch installation).

You'll get a public URL: `https://your-api.onrender.com`

## Test Deployment
```bash
curl https://your-api.onrender.com/health
```

## Next.js Frontend
Your Vercel frontend will call:
```javascript
const response = await fetch('https://your-api.onrender.com/api/recommend', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: "I want to build muscle",
    user_profile: { age: 24, sex: "Male", weight_kg: 75, height_cm: 178 }
  })
});
```
