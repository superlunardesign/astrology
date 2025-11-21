# Deployment Guide

## Deploy to Render

### Option 1: Using render.yaml (Recommended)

1. Push your code to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click "New +" and select "Blueprint"
4. Connect your GitHub repository
5. Render will automatically detect the `render.yaml` file and create the service
6. Your app will be deployed at: `https://transit-tracker.onrender.com`

### Option 2: Manual Setup

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" and select "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: transit-tracker
   - **Region**: Oregon (or your preferred region)
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `cd backend && gunicorn app:app`
   - **Environment Variables**:
     - `PYTHON_VERSION`: 3.11.0

5. Click "Create Web Service"

## Environment Variables

No sensitive environment variables are required. The app uses Swiss Ephemeris for astronomical calculations.

## Post-Deployment

After deployment:
1. Visit your app URL
2. The frontend will automatically load
3. All three natal charts (Christina, Julian, Davison) are pre-configured

## Accessing the App

- **Frontend**: `https://your-app.onrender.com/`
- **API Health Check**: `https://your-app.onrender.com/api/health`
- **API Docs**: See README.md for all available endpoints

## Free Tier Notes

Render's free tier:
- Spins down after 15 minutes of inactivity
- First request after spin-down may take 30-60 seconds
- Consider upgrading to paid plan for faster response times

## Keeping URL Private

For personal use, you can:
1. Don't share the Render URL publicly
2. Add basic HTTP authentication (requires code changes)
3. Use Render's Static Site password protection

## Troubleshooting

If deployment fails:
1. Check Render logs for errors
2. Ensure all dependencies are in requirements.txt
3. Verify the start command is correct
4. Swiss Ephemeris data will be automatically downloaded on first run

## Local Development

To run locally:
```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
cd backend
python app.py
```

App will be available at http://localhost:5000
