import os
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import secrets

# Railway specific logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Railway logs ke liye
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Railway environment variables
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'  # Railway tmp folder
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
Session(app)

# Global variables
followed_posts = []
last_fetch_time = None
fetch_lock = threading.Lock()
reminders = []
auto_refresh = False
refresh_thread = None

class SocialMediaMonitor:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
    def initialize_browser(self):
        """Initialize Playwright browser for Railway"""
        try:
            logger.info("Starting Playwright initialization...")
            self.playwright = sync_playwright().start()
            
            # Railway compatible launch options
            launch_options = {
                'headless': True,
                'args': [
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-setuid-sandbox',
                    '--single-process',
                    '--no-zygote',
                ]
            }
            
            self.browser = self.playwright.chromium.launch(**launch_options)
            self.context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            self.page = self.context.new_page()
            logger.info("Browser initialized successfully on Railway")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            return False
    
    def close_browser(self):
        """Close browser and cleanup"""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
    
    def fetch_followed_posts(self, platform="twitter"):
        """Fetch latest posts from followed accounts"""
        posts = []
        
        try:
            logger.info(f"Fetching posts from {platform}...")
            # Demo posts for testing (remove when using real platform)
            demo_posts = [
                {
                    'profile_name': 'Tech News',
                    'post_text': 'New AI breakthrough announced today! 🚀',
                    'post_time': datetime.now().isoformat(),
                    'post_link': f'https://{platform}.com/status/123',
                    'has_image': True,
                    'has_video': False,
                    'platform': platform,
                    'id': f'demo_1_{int(time.time())}'
                },
                {
                    'profile_name': 'Python Dev',
                    'post_text': 'Check out this amazing Python tutorial 📚',
                    'post_time': datetime.now().isoformat(),
                    'post_link': f'https://{platform}.com/status/456',
                    'has_image': False,
                    'has_video': True,
                    'platform': platform,
                    'id': f'demo_2_{int(time.time())}'
                },
                {
                    'profile_name': 'Web Designer',
                    'post_text': 'New CSS tricks that will blow your mind! ✨',
                    'post_time': datetime.now().isoformat(),
                    'post_link': f'https://{platform}.com/status/789',
                    'has_image': True,
                    'has_video': False,
                    'platform': platform,
                    'id': f'demo_3_{int(time.time())}'
                }
            ]
            
            logger.info(f"Fetched {len(demo_posts)} posts")
            return demo_posts
            
        except Exception as e:
            logger.error(f"Error fetching posts: {e}")
            return []

monitor = SocialMediaMonitor()

@app.route('/')
def index():
    """Main dashboard page"""
    if 'authenticated' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        dashboard_password = os.environ.get('DASHBOARD_PASSWORD', 'admin123')
        
        if password == dashboard_password:
            session['authenticated'] = True
            session['username'] = request.form.get('username', 'User')
            logger.info(f"User logged in: {session['username']}")
            return redirect(url_for('index'))
        else:
            logger.warning("Failed login attempt")
            return render_template('login.html', error="Invalid password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout"""
    username = session.get('username', 'Unknown')
    session.clear()
    logger.info(f"User logged out: {username}")
    return redirect(url_for('login'))

@app.route('/api/posts', methods=['GET'])
def get_posts():
    """API endpoint to get posts with filters"""
    if 'authenticated' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    filter_type = request.args.get('filter', 'all')
    
    # Filter posts
    filtered_posts = followed_posts.copy()
    
    if filter_type == 'images':
        filtered_posts = [p for p in filtered_posts if p.get('has_image')]
    elif filter_type == 'videos':
        filtered_posts = [p for p in filtered_posts if p.get('has_video')]
    elif filter_type == 'newest':
        filtered_posts.sort(key=lambda x: x.get('post_time', ''), reverse=True)
    
    return jsonify({
        'posts': filtered_posts,
        'last_fetch': last_fetch_time.isoformat() if last_fetch_time else None,
        'total_count': len(filtered_posts)
    })

@app.route('/api/fetch', methods=['POST'])
def fetch_posts():
    """Manual fetch posts"""
    if 'authenticated' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    global followed_posts, last_fetch_time
    
    with fetch_lock:
        try:
            logger.info("Manual fetch requested")
            
            # Initialize browser if needed
            if not monitor.page:
                if not monitor.initialize_browser():
                    return jsonify({'error': 'Failed to initialize browser'}), 500
            
            # Fetch posts
            new_posts = monitor.fetch_followed_posts()
            
            # Update global posts list
            followed_posts = new_posts
            last_fetch_time = datetime.now()
            
            logger.info(f"Manual fetch completed: {len(new_posts)} posts")
            return jsonify({
                'success': True,
                'count': len(new_posts),
                'timestamp': last_fetch_time.isoformat()
            })
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return jsonify({'error': str(e)}), 500

@app.route('/api/reminders', methods=['GET', 'POST', 'DELETE'])
def manage_reminders():
    """Manage reminder posts"""
    if 'authenticated' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if request.method == 'GET':
        return jsonify({'reminders': reminders})
    
    elif request.method == 'POST':
        data = request.json
        reminder = {
            'id': len(reminders) + 1,
            'type': data.get('type'),  # 'react' or 'reply'
            'post': data.get('post'),
            'created_at': datetime.now().isoformat()
        }
        reminders.append(reminder)
        logger.info(f"Reminder added: {reminder['type']}")
        return jsonify({'success': True, 'reminder': reminder})
    
    elif request.method == 'DELETE':
        global reminders
        reminder_id = request.args.get('id')
        reminders = [r for r in reminders if str(r.get('id')) != str(reminder_id)]
        return jsonify({'success': True})

@app.route('/api/open-browser', methods=['POST'])
def open_browser():
    """Open post in browser"""
    if 'authenticated' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    post_link = data.get('link')
    
    if post_link:
        try:
            logger.info(f"Opening browser for: {post_link}")
            return jsonify({'success': True, 'url': post_link})
        except Exception as e:
            logger.error(f"Error opening browser: {e}")
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'No link provided'}), 400

@app.route('/health')
def health_check():
    """Health check endpoint for Railway"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'Social Media Monitor'
    })

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
