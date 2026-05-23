import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Railway automatically sets PORT
    PORT = int(os.environ.get('PORT', 5000))
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-in-production')
    DASHBOARD_PASSWORD = os.environ.get('DASHBOARD_PASSWORD', 'admin123')
    
    # Session
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = '/tmp/flask_session'
    
    # Playwright settings
    CHROMIUM_ARGS = [
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--single-process',
    ]
