import os
from dotenv import load_dotenv
load_dotenv()
from subprocess import run
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from sqlalchemy.sql import roles, func
from models import db, User, Program, Activity, ProgramVote, ProgramComment, Follows, MakeJam, MakeJamSubmission, Notification
from supabase_utils import upload_image_to_supabase
from werkzeug.security import generate_password_hash, check_password_hash
import sys
from flask_login import current_user
from flask_migrate import Migrate
from verification import send_verification_email
# from flask_mail import Mail, Message  # Not used
import pytz
from models import MakeJam, SubmissionScore, UserProgramTier, UserBadge, Badge, ProgramView
from datetime import datetime, timedelta, date
from sqlalchemy import and_
import random
from requests_oauthlib import OAuth2Session
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

# os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Stopped using MailJet
# MAIL_KEY = os.getenv('MAIL_KEY')
# MAIL_SECRET = os.getenv('MAIL_SECRET')

# Stopped using Zoho Mail
# MAIL_USERNAME = os.getenv('MAIL_USERNAME', 'noreply@makecore.org')
# MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')

# Badges
BADGE_THRESHOLDS = {
    "programs": [1, 5, 10, 20],
    "comments": [5, 15, 30, 50],
    "upvotes": [5, 25, 50, 100],
}

app = Flask(__name__, static_folder="static", template_folder="templates")


@app.route("/sitemap.xml")
def sitemap():
    return send_file("sitemap.xml", mimetype="application/xml")


@app.route("/ads.txt")
def ads_txt():
    return send_file("ads.txt", mimetype="text/plain")

@app.context_processor # helps with injecting global variables
def inject_unread_count():
    try:
        user = None
        if 'user' in session:
            user = User.query.filter_by(username=session['user']).first()
        if user:
            unread_count = Notification.query.filter_by(user_id=user.id, is_read=False).count()
        else:
            unread_count = 0
    except Exception:
        unread_count = 0
    return dict(unread_count=unread_count)

@app.context_processor
def inject_show_ads():
    if 'user' in session:
        user = User.query.filter_by(username=session['user']).first()
        show_ads = user.show_ads

    else:
        show_ads = False
    return dict(show_ads=show_ads)

app.config.update(
    TEMPLATES_AUTO_RELOAD=True,
    SESSION_COOKIE_SECURE=True,  
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',  
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    SESSION_REFRESH_EACH_REQUEST=True
)

app.secret_key = os.getenv('APP_SECRET_KEY')

# Google OAuth
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
AUTH_BASE_URL = os.getenv('AUTH_BASE_URL')
TOKEN_URL = os.getenv('TOKEN_URL')
REDIRECT_URI = os.getenv('REDIRECT_URI')
SCOPE = ["openid", "email", "profile"]

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL'].replace(
    'postgres://', 
    'postgresql://',  # Important for SQLAlchemy 2.0+
) + "?sslmode=require&connect_timeout=10&keepalives=1&keepalives_idle=30"
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False



app.config['DEBUG'] = True


app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,  
    'pool_recycle': 300,    
    'pool_timeout': 30,     
    'max_overflow': 10      
}

db.init_app(app)

# Switched from SMTP to API (Render blocked SMTP Ports for Free Plan)
# app.config['MAIL_SERVER'] = 'smtp.zoho.com'
# app.config['MAIL_PORT'] = 587
# app.config['MAIL_USE_TLS'] = True
# app.config['MAIL_USE_SSL'] = False
# app.config['MAIL_USERNAME'] = MAIL_USERNAME
# app.config['MAIL_PASSWORD'] = MAIL_PASSWORD
# app.config['MAIL_DEFAULT_SENDER'] = ('MakeCore', MAIL_USERNAME)


# mail = Mail(app)

migrate = Migrate(app, db)




@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.route('/api/user/badges/collected/best/<username>')
def get_collected_badges(username):
    if not username:
        username = session['user']
    user = User.query.filter_by(username=username).first()
    
    if not user:
        return jsonify([])
    
    user_badges = (db.session.query(UserBadge, Badge)
                   .join(Badge, UserBadge.badge_id == Badge.id)
                   .filter(UserBadge.user_id == user.id)
                   .all())
    
    all_badges = Badge.query.order_by(Badge.badge_type, Badge.required_count).all()
    
    earned_badge_ids = {badge.id for _, badge in user_badges}
    
    best_badges = {}
    
    for badge in all_badges:
        if badge.id in earned_badge_ids:
            if (badge.badge_type not in best_badges or 
                badge.required_count > best_badges[badge.badge_type].get('required_count', 0)):
                best_badges[badge.badge_type] = {
                    'id': badge.id,
                    'name': badge.name,
                    'description': badge.description,
                    'icon_url': badge.icon_url,
                    'badge_type': badge.badge_type,
                    'required_count': badge.required_count,
                    'obtained': True
                }
    
    for badge in all_badges:
        if badge.badge_type not in best_badges:
            best_badges[badge.badge_type] = {
                'id': badge.id,
                'name': badge.name,
                'description': badge.description,
                'icon_url': badge.icon_url,
                'badge_type': badge.badge_type,
                'required_count': badge.required_count,
                'obtained': False
            }
            continue  
    
    return jsonify(list(best_badges.values()))

@app.route('/api/user/badges/data')
def get_user_badge_data():
    username=session['user']
    user_programs = Program.query.filter_by(developer=username).all()
    upvotes = sum(p.likes or 0 for p in user_programs)

    comments = 0
    for p in user_programs:
        comments += ProgramComment.query.filter_by(program_id=p.id).count()
    programs = len(Program.query.filter_by(developer=username).all())
    return jsonify({
        'upvote_count': upvotes,
        'comment_count': comments,
        'program_count': programs
    })
    

def award_badge(user_id, badge_name):
    user = User.query.get(user_id)
    badge = Badge.query.filter_by(name=badge_name).first()
    if not badge:
        # print("Badge not found")
        return False

    existing = UserBadge.query.filter_by(user_id=user.id, badge_id=badge.id).first()
    if existing:
        # print("User already has this badge")
        return False
    # print("Awarded")
    new_user_badge = UserBadge(user_id=user.id, badge_id=badge.id)
    db.session.add(new_user_badge)
    db.session.commit()
    return True



def check_and_award_badge(user):
    # Programs

    programs = Program.query.filter_by(developer=user.username).all()
    program_count = len(programs)
    newly_earned = None
    for count in BADGE_THRESHOLDS["programs"]:
        if program_count >= count:
            # print(f"Programs [{count}]")
            name = f"Programs [{count}]"
            if award_badge(user.id, name):
                badge = Badge.query.filter_by(name=name).first()
                if badge:
                    newly_earned = {
                        "name": badge.name,
                        "icon_url": badge.icon_url,
                        "description": badge.description
                    }
                break
                    

    if newly_earned:
        return newly_earned
    # Upvotes
    upvotes = sum(p.likes or 0 for p in programs)
    for count in BADGE_THRESHOLDS["upvotes"]:
        if upvotes >= count:
            # print(f"Upvotes [{count}]")
            name = f"Upvotes [{count}]"
            if award_badge(user.id, name):
                badge = Badge.query.filter_by(name=name).first()
                if badge:
                    newly_earned = {
                        "name": badge.name,
                        "icon_url": badge.icon_url,
                        "description": badge.description
                    }
                break
                    
    if newly_earned:
        return newly_earned
    # Comments
    comments = 0
    for p in programs:
        comments += ProgramComment.query.filter_by(program_id=p.id).count()

    for count in BADGE_THRESHOLDS["comments"]:
        if comments >= count:
            # print(f"Comments [{count}]")
            name = f"Comments [{count}]"
            if award_badge(user.id, name):
                badge = Badge.query.filter_by(name=name).first()
                if badge:
                    newly_earned = {
                        "name": badge.name,
                        "icon_url": badge.icon_url,
                        "description": badge.description
                    }
                break
                    
    if newly_earned:
        return newly_earned
    return None


@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

@app.route('/notifications')
def notifications_page():
    user = None
    if 'user' in session:
        user = User.query.filter_by(username=session['user']).first()
    if not user:
        flash('You must be logged in to view notifications', 'warning')
        return redirect(url_for('login'))
    notifs = Notification.query.filter_by(user_id=user.id).order_by(Notification.timestamp.desc()).all()
    pacific = pytz.timezone('US/Pacific')
    for notif in notifs:
        notif.timestamp_pdt = notif.timestamp.astimezone(pacific)
    return render_template('notifications.html', notifications=notifs)

@app.route('/notifications/mark_all_read', methods=['POST'])
def mark_all_notifications_read():
    user = None
    if 'user' in session:
        user = User.query.filter_by(username=session['user']).first()
    if not user:
        return '', 401
    Notification.query.filter_by(user_id=user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return '', 204


def create_notification(user_id, notif_type, message, related_url=None):
    notif = Notification(
        user_id=user_id,
        type=notif_type,
        message=message,
        related_url=related_url
    )
    db.session.add(notif)
    db.session.commit()

from flask_login import LoginManager, current_user
login_manager = LoginManager()
login_manager.init_app(app)

@app.before_request
def check_for_new_badges():
    username = session.get('user')
    if not username:
        return 

    if request.endpoint and ('api' in request.endpoint or request.endpoint == 'static'):
        return

    # Check for new badges
    user = User.query.filter_by(username=username).first()
    if user:
        badge_data = check_and_award_badge(user)
        if badge_data:
            create_notification(
                user_id=user.id,
                notif_type='badge',
                message=f"🎉 New badge: {badge_data['name']}",
                related_url=f"javascript:showBadgeModal({badge_data})"
            )
        # old before 3.1.0, refer to updates.txt
        # if badge_data and 'newBadge' not in session:
        #     session['newBadge'] = badge_data

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/program/<int:program_id>/vote', methods=['POST'])
def program_vote(program_id):
    program = Program.query.get_or_404(program_id)
    data = request.get_json()
    vote = data.get('vote')
    undo = data.get('undo', False)
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Not logged in'}), 403
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    user_vote = ProgramVote.query.filter_by(user_id=user.id, program_id=program_id, vote_type=vote).first()

    if vote == 'up':
        if undo:
            if user_vote:
                db.session.delete(user_vote)
                program.likes = max(0, program.likes - 1)
        else:
            if not user_vote:
                new_vote = ProgramVote(user_id=user.id, program_id=program_id, vote_type='up')
                db.session.add(new_vote)
                program.likes += 1
    elif vote == 'down':
        if undo:
            if user_vote:
                db.session.delete(user_vote)
                program.dislikes = max(0, program.dislikes - 1)
        else:
            if not user_vote:
                new_vote = ProgramVote(user_id=user.id, program_id=program_id, vote_type='down')
                db.session.add(new_vote)
                program.dislikes += 1
    db.session.commit()
    owner = User.query.filter_by(username=program.developer).first()

    if not undo:
        create_notification(owner.id, 'upvote' if vote == 'up' else 'downvote', f'{user.username} has {"upvoted" if vote == "up" else "downvoted"} your program {program.name}', f'/program/{program.id}')
    return jsonify({'likes': program.likes, 'dislikes': program.dislikes})

@app.route('/program/<int:program_id>/comment', methods=['POST'])
def program_comment(program_id):
    data = request.get_json()
    content = data.get('content', '').strip()
    username = session.get('user')
    if not content:
        return jsonify({'error': 'No content'}), 400
    user = User.query.filter_by(username=username).first() if username else None
    user_id = user.id if user else None
    if not user_id:
        return jsonify({'error': 'Not logged in'}), 403
    comment = ProgramComment(content=content, user_id=user_id, program_id=program_id)
    db.session.add(comment)
    db.session.commit()
    # Notify project owner if not self
    program = Program.query.get(program_id)
    if program and program.developer and user and program.developer != user.username:
        owner = User.query.filter_by(username=program.developer).first()
        if owner:
            
            create_notification(
                user_id=owner.id,
                notif_type='comment',
                message=f"{user.username} commented on your program <span class='studio-pill'>{program.name}</span>: &quot;{content}&quot; ",
                related_url=url_for('program_detail', program_id=program.id)
            )
    return jsonify({'success': True, 'user': user.username, 'text': content})

from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import flash, redirect, url_for, render_template, request, session

serializer = URLSafeTimedSerializer(app.secret_key)

@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            token = serializer.dumps(user.email, salt='reset-password')
            reset_link = url_for('reset_password', token=token, _external=True)

            from flask_mail import Message
            html_content = f'''
                <div style="font-family: 'Segoe UI', sans-serif; max-width: 480px; margin: auto; padding: 20px; background: linear-gradient(135deg, #fff6ee 60%, #ffd1b3 100%); border-radius: 16px;">
                    <h2 style="color: #b04a18; text-align: center; margin-bottom: 18px;">Reset Your Password</h2>
                    <p style="font-size: 16px; color: #a74a1e; text-align: center;">Hi <b>{user.username}</b>,</p>
                    <p style="font-size: 16px; color: #b04a18; text-align: center;">Click the button below to reset your password. This link will expire in 1 hour.</p>
                    <div style="text-align:center; margin: 32px 0;">
                        <a href="{reset_link}" style="display:inline-block; background: linear-gradient(90deg, #ff935d 60%, #ffae85 100%); color:#fff; font-weight:600; padding: 14px 32px; font-size: 1.1rem; border-radius: 8px; text-decoration:none; box-shadow:0 2px 8px #ffb36a50;">Reset Password</a>
                    </div>
                    <p style="font-size: 14px; color: #b04a18; text-align: center;">If you did not request a password reset, you can safely ignore this email.</p>
                </div>
            '''
            msg = Message(
                subject='Reset Your MakeCore Password',
                recipients=[user.email],
                html=html_content
            )
            try:
                mail.send(msg)
                flash('A reset link has been sent to your email.', 'success')
            except Exception as e:
                flash('Error sending email: ' + str(e), 'danger')
        else:
            flash('If this email exists, reset instructions have been sent.', 'info')
        return render_template('forgot_sent.html', email=email)
    return render_template('forgot.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='reset-password', max_age=3600)
    except (SignatureExpired, BadSignature):
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot'))
    if request.method == 'POST':
        password = request.form['password']
        password2 = request.form['password2']
        if password != password2:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html')
        user = User.query.filter_by(email=email).first()
        if user:
            from werkzeug.security import generate_password_hash
            user.password_hash = generate_password_hash(password)
            db.session.commit()
            flash('Your password has been reset. You can now log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('User not found.', 'danger')
            return redirect(url_for('forgot'))
    return render_template('reset_password.html')

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        # Check if it's a login or signup form based on presence of email field
        if 'email' in request.form:
            # Signup form
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
            if User.query.filter_by(username=username).first():
                flash('Username already exists', 'warning')
                return render_template('auth.html')
            if User.query.filter_by(email=email).first():
                flash('Email already registered', 'warning')
                return render_template('auth.html')

            code = str(random.randint(1000, 9999))
            session['pending_user'] = {
                'username': username,
                'email': email,
                'password_hash': generate_password_hash(password, method='pbkdf2:sha256'),
                'code': code
            }
            session.modified = True
            
            if send_verification_email(email, code):
                flash('A verification code has been sent to your email.', 'info')
                return redirect(url_for('verify'))
            else:
                flash('Failed to send verification email. Please try again later.', 'danger')
        else:
            # Login form
            username = request.form['username']
            password = request.form['password']
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                session['user'] = username
                flash(("Logged In", "You have logged in successfully"), "success")
                return redirect(url_for('dashboard'))
            flash('Invalid credentials', 'danger')
    return render_template('auth.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user'] = username
            flash(("Logged In", "You have logged in successfully"), "success")
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'danger')
        return render_template('auth.html')
    else:  
        return render_template('auth.html')

@app.route('/google-login')
def google_login():
    google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=SCOPE)
    authorization_url, state = google.authorization_url(AUTH_BASE_URL, access_type='offline', prompt='consent')
    session['oauth_state'] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback(): # for Google OAuth
    try:
        google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
        token = google.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, authorization_response=request.url)
        session["oauth_token"] = token
        resp = google.get("https://www.googleapis.com/oauth2/v1/userinfo")
        user_info = resp.json()
        
        google_id = user_info.get('id')
        email = user_info.get('email')
        name = user_info.get('name')
        picture = user_info.get('picture')
        
        if not email:
            flash('Unable to get email from Google account', 'error')
            return redirect(url_for('login'))
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            session['user'] = user.username
            flash('Successfully logged in with Google!', 'success')
            return redirect(url_for('dashboard'))
        else:
            # Store Google user info in session for username selection
            session['google_user'] = {
                'google_id': google_id,
                'email': email,
                'name': name,
                'picture': picture
            }
            # Suggest username based on email
            suggested_username = email.split('@')[0] if email else name.lower().replace(' ', '')
            return redirect(url_for('google_username', suggested=suggested_username))
            
    except Exception as e:
        flash(f'Error during Google authentication: {str(e)}', 'error')
        return redirect(url_for('login'))

@app.route('/google-username')
def google_username():
    """Show username selection page for new Google users"""
    google_user = session.get('google_user')
    if not google_user:
        flash('No Google user data found. Please try logging in again.', 'error')
        return redirect(url_for('login'))
    
    suggested = request.args.get('suggested', '')
    return render_template('google_username.html', 
                         google_user=google_user, 
                         suggested_username=suggested)

@app.route('/google-username', methods=['POST'])
def create_google_user():
    google_user = session.get('google_user')
    if not google_user:
        flash('No Google user data found. Please try logging in again.', 'error')
        return redirect(url_for('login'))
    
    username = request.form['username'].strip()
    password = request.form.get('password', '').strip()
    
    if not username:
        flash('Username is required', 'error')
        return redirect(url_for('google_username'))
    
    if len(username) < 3:
        flash('Username must be at least 3 characters long', 'error')
        return redirect(url_for('google_username'))
    
    if len(username) > 12:
        flash('Username must be less than 12 characters', 'error')
        return redirect(url_for('google_username'))
    
    if User.query.filter_by(username=username).first():
        flash('Username is already taken. Please choose another.', 'error')
        return redirect(url_for('google_username'))
    
    password_hash = None
    if password:
        if len(password) < 6:
            flash('Password must be at least 8 characters long', 'error')
            return redirect(url_for('google_username'))
        password_hash = generate_password_hash(password)
    
    try:
        new_user = User(
            username=username,
            email=google_user['email'],
            password_hash=password_hash,  
            google_id=google_user['google_id'],
            profile_pic_url=google_user['picture'],
            is_verified=True 
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        from supabase_utils import create_user_folders_in_supabase, upload_image_to_supabase
        create_user_folders_in_supabase(new_user.username)
        
        try:
            import requests
            from io import BytesIO
            
            response = requests.get(google_user['picture'])
            if response.status_code == 200:
        
                image_data = BytesIO(response.content)
                image_data.name = f"{username}_profile.jpg"
                
                uploaded_url = upload_image_to_supabase(image_data, folder=f"{username}/profile")
                if uploaded_url:
            
                    new_user.profile_pic_url = uploaded_url
                    new_user.profile_pic_name = f"{username}_profile.jpg"
                    db.session.commit()


        except Exception as e:
            print(f"[Google OAuth] Error handling profile picture: {e}")
        
        session.pop('google_user', None)
        
        session['user'] = new_user.username
        if password:
            flash('Account created successfully! You can now login with Google or your username/password.', 'success')
        else:
            flash('Account created successfully with Google!', 'success')
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        flash(f'Error creating account: {str(e)}', 'error')
        return redirect(url_for('google_username'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'warning')
            return redirect(url_for('signup'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'warning')
            return redirect(url_for('signup'))

        code = str(random.randint(1000, 9999))
        session['pending_user'] = {
            'username': username,
            'email': email,
            'password_hash': generate_password_hash(password, method='pbkdf2:sha256'),
            'code': code
        }
        session.modified = True
        
        if send_verification_email(email, code):
            flash('A verification code has been sent to your email.', 'info')
            return redirect(url_for('verify'))
        else:
            flash('Failed to send verification email. Please try again later.', 'danger')

    return render_template('auth.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        data = request.get_json()
        code = data.get('code')
        pending = session.get('pending_user')
        if not pending:
            return {'success': False, 'error': 'No pending signup'}, 400
        if code == pending.get('code'):
            # Create user
            user = User(username=pending['username'], email=pending['email'], password_hash=pending['password_hash'])
            db.session.add(user)
            db.session.commit()
            from supabase_utils import create_user_folders_in_supabase
            create_user_folders_in_supabase(user.username)
            session.pop('pending_user', None)
            return {'success': True}
        return {'success': False}, 200
    return render_template('verify.html')

@app.route('/get_pending_code')
def get_pending_code():
    pending = session.get('pending_user')
    if pending:
        return {'code': pending.get('code'), 'email': pending.get('email')}
    return {'code': None, 'email': None}

@app.route('/resend_verification', methods=['POST'])
def resend_verification():
    pending = session.get('pending_user')
    if pending:
        email = pending.get('email')
        code = pending.get('code')
        if send_verification_email(email, code):
            return {'success': True, 'message': 'Verification code has been resent', 'type': 'info'}
        else:
            return {'success': False, 'message': 'Failed to resend verification email. Please try again later.', 'type': 'danger'}
    else:
        return {'success': False, 'message': 'No pending verification found. Please sign up again.', 'type': 'warning'}


@app.route('/logout')
def logout():
    session.pop('user', None)
    flash(("Logged Out", "You have been logged out successfully."), "success")
    return redirect(url_for('home'))

@app.route('/')
def home():
    username = session.get('user')
    return render_template('index.html', username=username, current_page="home")

@app.route('/mindmap')
def mindmap():
    return render_template('mindmap.html')

from functools import wraps



@app.route('/studios/<int:studio_id>/join', methods=['POST'])
def join_studio(studio_id):
    user = User.query.filter_by(username=session.get('user')).first()
    if not user:
        flash('You must be logged in to follow a studio', 'warning')
        return redirect(url_for('login'))
    studio = db.session.get(Studio, studio_id)
    if not studio:
        abort(404)
    existing = StudioMembership.query.filter_by(user_id=user.id, studio_id=studio_id).first()
    if existing:
        if not existing.accepted:
            existing.accepted = True
            existing.invited = False
            db.session.commit()
            flash('You are now a contributor to this studio!', 'success')
        else:
            flash('You are already following this studio.', 'info')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='curators'))
    membership = StudioMembership(user_id=user.id, studio_id=studio_id, role='contributor', accepted=True)
    db.session.add(membership)
    db.session.commit()
    flash('You are now a contributor to this studio!', 'success')
    return redirect(url_for('studio_detail', studio_id=studio_id, tab='curators'))

# def login_required(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         if 'user' not in session:
#             flash('Please log in to access this page.', 'warning')
#             return redirect(url_for('login', next=request.endpoint))
#         return f(*args, **kwargs)
#     return decorated_function

from sqlalchemy import case, and_, or_
from sqlalchemy import func

@app.route('/programs')
def programs():
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'upvotes')
    order = request.args.get('order', 'desc')
    filter_logic = request.args.get('filter_logic', 'any')
    source = request.args.get('source', 'all').lower()
    
    page = request.args.get('page', 1, type=int)
    per_page = 24 
    
    query = db.session.query(
        Program,
        func.count(ProgramComment.id).label('comment_count')
    ).outerjoin(
        ProgramComment, Program.id == ProgramComment.program_id
    ).group_by(Program.id)
    
    if search:
        query = query.filter(Program.name.ilike(f'%{search}%'))

    if source == 'makecode':
        query = query.filter(Program.program_url.ilike('%makecode%'))
    elif source == 'scratch':
        query = query.filter(Program.program_url.ilike('%scratch%'))
    
    filter_conditions = []
    having_conditions = []
    
    def add_filter_condition(field, op, val):
        if not val or not op or op == '-':
            return
            
        try:
            val = int(val)
        except (ValueError, TypeError):
            return
            
        where_fields = {
            'upvotes': Program.likes,
            'downvotes': Program.dislikes,
            'views': Program.views
        }
        
        having_fields = {
            'comments': func.count(ProgramComment.id)
        }
        
        if field in where_fields:
            field_expr = where_fields[field]
            if op == 'greater':
                filter_conditions.append(field_expr > val)
            elif op == 'less':
                filter_conditions.append(field_expr < val)
            elif op == 'equal':
                filter_conditions.append(field_expr == val)
            elif op == 'not-equal':
                filter_conditions.append(field_expr != val)
        elif field in having_fields:
            field_expr = having_fields[field]
            if op == 'greater':
                having_conditions.append(field_expr > val)
            elif op == 'less':
                having_conditions.append(field_expr < val)
            elif op == 'equal':
                having_conditions.append(field_expr == val)
            elif op == 'not-equal':
                having_conditions.append(field_expr != val)
    
    for field in ['upvotes', 'downvotes', 'views', 'comments']:
        op = request.args.get(f'{field}_op')
        val = request.args.get(f'{field}_val')
        add_filter_condition(field, op, val)
    
    if filter_conditions:
        if filter_logic.lower() == 'all':
            query = query.filter(and_(*filter_conditions))
        else: 
            query = query.filter(or_(*filter_conditions))
    
    if having_conditions:
        if filter_logic.lower() == 'all':
            query = query.having(and_(*having_conditions))
        else:
            query = query.having(or_(*having_conditions))
    
    sort_field = {
        'date': Program.last_updated,
        'upvotes': Program.likes,
        'downvotes': Program.dislikes,
        'comments': func.count(ProgramComment.id),
        'views': Program.views
    }.get(sort_by, Program.last_updated)
    
    if order == 'asc':
        sort_field = sort_field.asc()
    else:
        sort_field = sort_field.desc()
    
    query = query.order_by(sort_field)
    programs = query.paginate(page=page, per_page=per_page, error_out=False)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        programs_list = [{
            'id': program.id,
            'name': program.name,
            'description': program.description or '',
            'likes': program.likes or 0,
            'dislikes': program.dislikes or 0,
            'comment_count': comment_count or 0,
            'views': program.views or 0,
            'image_url': program.image_url or '/static/images/placeholder.png',
            'program_url': program.program_url or '#',
            'last_updated': program.last_updated.isoformat() if program.last_updated else None
        } for program, comment_count in programs.items]
        
        response_data = {
            'programs': programs_list,
            'has_next': programs.has_next,
            'page': programs.page,
            'pages': programs.pages,
            'total': programs.total
        }
        
        return jsonify(response_data)
    
    program_data = [(program, comment_count) for program, comment_count in programs.items]
    
    played_count = 0
    total_programs = db.session.query(func.count(Program.id)).scalar() or 0
    try:
        user = User.query.filter_by(username=session.get('user')).first()
        if user:
            played_count = db.session.query(func.count(ProgramView.program_id)) \
                .filter(ProgramView.user_id == user.id) \
                .scalar() or 0
    except Exception:
        played_count = 0

    return render_template('programs.html', 
                         program_data=program_data,
                         pagination=programs,
                         current_sort=sort_by,
                         current_order=order,
                         search_query=search,
                         played_count=played_count,
                         total_programs=total_programs,
                         username=session.get('user'))

# Random program redirect
@app.route('/program/random')
def program_random():
    random_program = Program.query.order_by(func.random()).first()
    if random_program:
        return redirect(url_for('program_detail', program_id=random_program.id))
    flash('No programs available yet.', 'info')
    return redirect(url_for('programs'))

from models import Studio, StudioMembership, StudioProject, StudioComment, StudioActivity, Comment
from sqlalchemy import or_

@app.route('/api/usernames')
def get_usernames():
    users = User.query.with_entities(User.username).all()
    usernames = [u[0] for u in users]
    return jsonify({'usernames': usernames})

@app.context_processor
def inject_user():
    user = None
    if 'user' in session:
        user = User.query.filter_by(username=session['user']).first()
    return dict(user=user)


def get_studio_role(user_id, studio_id):
    membership = StudioMembership.query.filter_by(user_id=user_id, studio_id=studio_id, accepted=True).first()
    return membership.role if membership else None

def studio_permission_required(studio_id, roles):
    def decorator(func):
        def wrapper(*args, **kwargs):
            user = User.query.filter_by(username=session.get('user')).first()
            if not user:
                flash('You must be logged in.', 'warning')
                return redirect(url_for('login'))
            role = get_studio_role(user.id, studio_id)
            if role not in roles:
                flash('Insufficient permissions.', 'danger')
                return redirect(url_for('studios'))
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator


@app.route('/blueprint')
def blueprint():
    return render_template('blueprint.html')

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    from flask import request, render_template, flash, redirect, url_for
    if request.method == 'POST':
        feedback_type = request.form.get('feedback_type', 'General')
        feedback_text = request.form.get('feedback_text', '').strip()
        feedback_email = request.form.get('feedback_email', '').strip()
        if not feedback_text:
            flash('Feedback cannot be empty.', 'danger')
            return render_template('feedback.html')
        subject = f"[Feedback] {feedback_type}"
        body = f"Feedback Type: {feedback_type}\n\nFeedback:\n{feedback_text}\n\nEmail: {feedback_email if feedback_email else 'N/A'}"
        try:
            msg = Message(subject, recipients=["1makecore1@gmail.com"], body=body)
            mail.send(msg)
            flash('Thank you for your feedback!', 'success')
            return render_template('feedback.html', thank_you=True)
        except Exception as e:
            flash('Error sending feedback. Please try again later.', 'danger')
            return render_template('feedback.html')
    return render_template('feedback.html')


@app.route('/tos')
def tos():
    return render_template('tos.html')

@app.route('/studios')
def studios():
    user = User.query.filter_by(username=session.get('user')).first()
    public_studios = Studio.query.filter_by(visibility='public').all()
    member_studios = StudioMembership.query.filter_by(user_id=user.id, accepted=True).all() if user else []
    return render_template('studios.html', public_studios=public_studios, member_studios=member_studios)

@app.route('/studios/create', methods=['GET', 'POST'])
def create_studio():
    user = User.query.filter_by(username=session.get('user')).first()
    if not user:
        flash('You must be logged in to create a studio', 'warning')
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title'][:100]
        description = request.form['description']
        thumbnail = request.files.get('thumbnail')
        visibility = request.form.get('visibility', 'public')
        thumbnail_url = None
        if thumbnail and allowed_file(thumbnail.filename):
            thumbnail_url = upload_image_to_supabase(thumbnail, folder=f'studios/{title}/thumbnail')
        anyone_can_add = 'anyone_can_add' in request.form
        studio = Studio(title=title, description=description, thumbnail_url=thumbnail_url, visibility=visibility, owner_id=user.id, anyone_can_add=anyone_can_add)
        db.session.add(studio)
        db.session.commit()
        # Creator membership
        membership = StudioMembership(user_id=user.id, studio_id=studio.id, role='creator', accepted=True)
        db.session.add(membership)
        db.session.commit()
        flash('Studio created!', 'success')
        return redirect(url_for('studio_detail', studio_id=studio.id))
    return render_template('studio_create.html')

@app.route('/studios/<int:studio_id>')
def studio_detail(studio_id):
    studio = db.session.get(Studio, studio_id)
    if not studio:
        abort(404)
    user = User.query.filter_by(username=session.get('user')).first()
    role = get_studio_role(user.id, studio_id) if user else None
    projects = []
    for sp in studio.projects:
        if sp is not None:
            program = Program.query.get(sp.program_id)
            if program:
                # Load the user relationship
                program.user = User.query.filter_by(username=program.developer).first()
                projects.append(program)
    memberships = StudioMembership.query.filter_by(studio_id=studio_id).all()
    managers = [m for m in memberships if m.role in ('manager', 'creator') and m.accepted]
    contributors = [m for m in memberships if m.role == 'contributor' and m.accepted]
    pending = [m for m in memberships if m.role == 'contributor' and not m.accepted]
    comments = StudioComment.query.filter_by(studio_id=studio_id).order_by(StudioComment.created_at.desc()).all()
    by_id = {c.id: c for c in comments}
    roots = []
    for c in comments:
        if c.user_id:
            c.user = User.query.get(c.user_id)
        if c.parent_id and c.parent_id in by_id:
            parent = by_id[c.parent_id]
            if not hasattr(parent, 'children'):
                parent.children = []
            parent.children.append(c)
        else:
            roots.append(c)
    user_projects = Program.query.filter_by(developer=user.username).order_by(Program.last_updated.desc()).all() if user else []
    is_owner = user.id == studio.owner_id if user else False
    user_studio_project_ids = [p.id for p in projects if p is not None and user and p.developer == user.username]
    from flask_login import current_user

    activities = db.session.query(StudioActivity, User, Program) \
        .join(User, StudioActivity.user_id == User.id) \
        .outerjoin(Program, StudioActivity.project_id == Program.id) \
        .filter(StudioActivity.studio_id == studio_id) \
        .order_by(StudioActivity.timestamp.desc()) \
        .limit(30).all()

    if request.args.get('ajax') == '1':

        from flask import render_template_string
        html = render_template('studio_detail.html', studio=studio, projects=projects, managers=managers, contributors=contributors, pending=pending, comments=comments, role=role, current_user=current_user, user_projects=user_projects, is_owner=is_owner, user_studio_project_ids=user_studio_project_ids, activities=activities)

        import re
        match = re.search(r'<div class="studio-tab-content" id="tab-activity".*?</div>', html, re.DOTALL)
        return match.group(0) if match else '', 200, {'Content-Type': 'text/html'}
    return render_template('studio_detail.html', studio=studio, projects=projects, managers=managers, contributors=contributors, pending=pending, comments=roots, role=role, current_user=current_user, user_projects=user_projects, is_owner=is_owner, user_studio_project_ids=user_studio_project_ids, activities=activities)



@app.route('/studios/<int:studio_id>/toggle_anyone_can_add', methods=['POST'])
def toggle_anyone_can_add(studio_id):
    user = User.query.filter_by(username=session.get('user')).first()
    studio = db.session.get(Studio, studio_id)
    if not studio or not user:
        abort(404)
    role = get_studio_role(user.id, studio_id)
    if role != 'creator':
        flash('Only the studio creator can change this setting.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id))

    anyone_can_add = request.form.get('anyone_can_add') == 'on'
    studio.anyone_can_add = anyone_can_add
    db.session.commit()
    flash('Studio updated: Anyone can add projects is now {}.'.format('enabled' if anyone_can_add else 'disabled'), 'success')
    return redirect(url_for('studio_detail', studio_id=studio.id))

@app.route('/studios/<int:studio_id>/edit', methods=['GET', 'POST'])
def edit_studio(studio_id):
    studio = db.session.get(Studio, studio_id)
    if not studio:
        abort(404)
    user = User.query.filter_by(username=session.get('user')).first()
    role = get_studio_role(user.id, studio_id)
    if role not in ['creator', 'manager']:
        flash('Insufficient permissions.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))
    if request.method == 'POST':
        studio.title = request.form['title'][:100]
        studio.description = request.form['description']
        visibility = request.form.get('visibility', 'public')
        studio.visibility = visibility
        thumbnail = request.files.get('thumbnail')
        if thumbnail and allowed_file(thumbnail.filename):
            studio.thumbnail_url = upload_image_to_supabase(thumbnail, folder=f'studios/{studio.title}/thumbnail')
        db.session.commit()
        flash('Studio updated!', 'success')
        return redirect(url_for('studio_detail', studio_id=studio.id))
    return render_template('studio_edit.html', studio=studio)

@app.route('/studios/<int:studio_id>/delete', methods=['POST'])
def delete_studio(studio_id):
    studio = db.session.get(Studio, studio_id)
    if not studio:
        abort(404)
    user = User.query.filter_by(username=session.get('user')).first()
    role = get_studio_role(user.id, studio_id)
    if role != 'creator':
        flash('Only the creator can delete this studio.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))
    db.session.delete(studio)
    db.session.commit()
    flash('Studio deleted.', 'info')
    return redirect(url_for('studios'))

# --- Project Management ---
@app.route('/studios/<int:studio_id>/add_project', methods=['POST'])
def add_project_to_studio(studio_id):
    user = User.query.filter_by(username=session.get('user')).first()
    studio = db.session.get(Studio, studio_id)
    if not studio:
        abort(404)
    role = get_studio_role(user.id, studio_id)
    if role not in ['creator', 'manager', 'curator', 'owner', 'contributor'] and not studio.anyone_can_add:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403
        flash('Insufficient permissions to add projects.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))
    project_id = request.form.get('project_id') or (request.json.get('project_id') if request.is_json else None)
    if not project_id:
        if request.is_json:
            return jsonify({'success': False, 'error': 'No project specified.'}), 400
        flash('No project specified.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))
    project = db.session.get(Program, project_id)
    if not project:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Project not found.'}), 404
        flash('Project not found.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))
    existing = StudioProject.query.filter_by(studio_id=studio_id, program_id=project.id).first()
    if existing:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Project already in studio.'}), 409
        flash('Project already in studio.', 'warning')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))
    studio_project = StudioProject(studio_id=studio_id, program_id=project.id, added_by=user.id)
    db.session.add(studio_project)
    db.session.commit()
    activity = StudioActivity(studio_id=studio_id, user_id=user.id, project_id=project.id, action='add')
    db.session.add(activity)
    db.session.commit()
    if studio.owner_id and user and studio.owner_id != user.id:
        owner = User.query.get(studio.owner_id)
        if owner:
            create_notification(
                user_id=owner.id,
                notif_type='studio_activity',
                message=f"{user.username} added <b>{project.name}</b> to your studio <b>{studio.title}</b>.",
                related_url=url_for('studio_detail', studio_id=studio.id)
            )
    if request.is_json:
        developer = User.query.filter_by(username=project.developer).first()

        return jsonify({
            'success': True,
            'developer': {
                'username': developer.username if developer else project.developer,
                'profile_pic_url': developer.profile_pic_url if developer and developer.profile_pic_url else None
            }
        })
    flash('Project added to studio!', 'success')
    return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))

@app.route('/studios/<int:studio_id>/remove_project/<int:project_id>', methods=['POST'])
def remove_project_from_studio(studio_id, project_id):
    user = User.query.filter_by(username=session.get('user')).first()
    studio = db.session.get(Studio, studio_id)
    if not studio:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Studio not found.'}), 404
        abort(404)
    role = get_studio_role(user.id, studio_id)
    if role not in ['creator', 'manager', 'contributor'] and not studio.anyone_can_add:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Insufficient permissions to remove projects.'}), 403
        flash('Only managers, creators, or contributors can remove projects.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))
    studio_project = StudioProject.query.filter_by(studio_id=studio_id, program_id=project_id).first()
    if not studio_project:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Project not found in studio.'}), 404
        flash('Project not found in studio.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))
    
    db.session.delete(studio_project)
    db.session.commit()
    
    # Record activity
    activity = StudioActivity(studio_id=studio_id, user_id=user.id, project_id=project_id, action='remove')
    db.session.add(activity)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': 'Project removed from studio.'})
    
    flash('Project removed from studio.', 'info')
    return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))

# --- Member Management ---
@app.route('/studios/<int:studio_id>/invite', methods=['POST'])
def invite_member(studio_id):
    user = User.query.filter_by(username=session.get('user')).first()
    studio = db.session.get(Studio, studio_id)
    if not studio:
        abort(404)
    role = get_studio_role(user.id, studio_id)
    if role not in ['creator', 'manager']:
        flash('Only managers or the creator can invite members.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='curators'))
    invite_username = request.form.get('invite_username')
    invitee = User.query.filter_by(username=invite_username).first()
    if not invitee:
        flash('User does not exist.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='curators'))
    if StudioMembership.query.filter_by(user_id=invitee.id, studio_id=studio_id).first():
        flash('User already a member or invited.', 'warning')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='curators'))
    membership = StudioMembership(user_id=invitee.id, studio_id=studio_id, role='contributor', invited=True, accepted=False)
    db.session.add(membership)
    
    # Send notification to the invited user
    create_notification(
        user_id=invitee.id,
        notif_type='studio_invite',
        message=f"You've been invited to contribute to <span class='studio-pill'>{studio.title}</span> by {user.username}",
        related_url=url_for('studio_detail', studio_id=studio_id)
    )
    
    db.session.commit()
    flash(f"{invite_username} has been invited as a contributor!", 'info')
    return redirect(url_for('studio_detail', studio_id=studio_id, tab='curators'))

@app.route('/studios/<int:studio_id>/accept_invite', methods=['POST'])
def accept_invite(studio_id):
    user = User.query.filter_by(username=session.get('user')).first()
    membership = StudioMembership.query.filter_by(user_id=user.id, studio_id=studio_id, invited=True, accepted=False).first()
    if not membership:
        flash('No pending invitation.', 'danger')
        return redirect(url_for('studios'))
    membership.accepted = True
    membership.invited = False
    
    # Get studio info for notification
    studio = db.session.get(Studio, studio_id)
    
    # Send notification to studio owner/creator
    studio_owner = User.query.get(studio.owner_id)
    if studio_owner and studio_owner.id != user.id:  # Don't notify yourself
        create_notification(
            user_id=studio_owner.id,
            notif_type='studio_accept',
            message=f"{user.username} has accepted your invitation to contribute to <span class='studio-pill'>{studio.title}</span>",
            related_url=url_for('studio_detail', studio_id=studio_id, tab='curators')
        )
    
    # Also notify managers (excluding the owner and the user who accepted)
    managers = StudioMembership.query.filter_by(studio_id=studio_id, role='manager', accepted=True).all()
    for manager_membership in managers:
        if manager_membership.user_id != user.id and manager_membership.user_id != studio.owner_id:
            create_notification(
                user_id=manager_membership.user_id,
                notif_type='studio_accept',
                message=f"{user.username} has accepted the invitation to contribute to <span class='studio-pill'>{studio.title}</span>",
                related_url=url_for('studio_detail', studio_id=studio_id, tab='curators')
            )
    
    db.session.commit()
    flash('You have joined the studio!', 'success')
    return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))

@app.route('/studios/<int:studio_id>/promote/<int:member_id>', methods=['POST'])
def promote_member(studio_id, member_id):
    user = User.query.filter_by(username=session.get('user')).first()
    studio = db.session.get(Studio, studio_id)
    if not studio:
        abort(404)
    role = get_studio_role(user.id, studio_id)
    if role not in ['creator', 'manager']:
        flash('Only managers or the creator can promote.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='curators'))
    membership = StudioMembership.query.filter_by(user_id=member_id, studio_id=studio_id).first()
    if not membership or membership.role != 'contributor':
        flash('Can only promote contributors.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='curators'))
    membership.role = 'manager'
    db.session.commit()
    flash('Contributor promoted to manager!', 'success')
    return redirect(url_for('studio_detail', studio_id=studio_id, tab='curators'))

@app.route('/studios/<int:studio_id>/remove_member/<int:member_id>', methods=['POST'])
def remove_member(studio_id, member_id):
    user = User.query.filter_by(username=session.get('user')).first()
    studio = db.session.get(Studio, studio_id)
    if not studio:
        abort(404)
    role = get_studio_role(user.id, studio_id)
    membership = StudioMembership.query.filter_by(user_id=member_id, studio_id=studio_id).first()
    if not membership:
        flash('Member not found.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))
    if membership.role == 'creator':
        flash('Cannot remove the creator.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))
    if role not in ['creator', 'manager']:
        flash('Only managers or the creator can remove members.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))

    removed_user = User.query.get(member_id)
    
    if removed_user and membership.invited and not membership.accepted:
        create_notification(
            user_id=removed_user.id,
            notif_type='studio_invite_revoked',
            message=f"Your invitation to contribute to <span class='studio-pill'>{studio.title}</span> has been revoked",
            related_url=url_for('studios')
        )
    
    db.session.delete(membership)
    db.session.commit()
    flash('Member removed.', 'info')
    return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))

@app.route('/studios/<int:studio_id>/leave', methods=['POST'])
def leave_studio(studio_id):
    user = User.query.filter_by(username=session.get('user')).first()
    membership = StudioMembership.query.filter_by(user_id=user.id, studio_id=studio_id).first()
    if not membership:
        flash('Not a member.', 'danger')
        return redirect(url_for('studios'))
    if membership.role == 'creator':
        flash('Creator cannot leave the studio.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))
    db.session.delete(membership)
    db.session.commit()
    flash('You left the studio.', 'info')
    return redirect(url_for('studios'))

# --- Follow/Unfollow System ---

@app.route('/follow/<int:user_id>', methods=['POST'])
def follow(user_id):
    if 'user' not in session:
        flash('You must be logged in to follow users', 'warning')
        return redirect(url_for('login'))
    follower = User.query.filter_by(username=session['user']).first()
    followed = User.query.get_or_404(user_id)
    if follower.id == followed.id:
        flash('You cannot follow yourself.', 'warning')
        return redirect(url_for('dashboard_user', username=followed.username))
    existing = Follows.query.filter_by(follower_id=follower.id, followed_id=followed.id).first()
    if not existing:
        follow = Follows(follower_id=follower.id, followed_id=followed.id)
        db.session.add(follow)
      
        notif_msg = f"{follower.username} has started following you."
        create_notification(followed.id, "follow", notif_msg)

        flash(f'You are now following {followed.username}!', 'success')
    else:
        flash('You are already following this user.', 'info')
    return redirect(url_for('dashboard_user', username=followed.username))

@app.route('/unfollow/<int:user_id>', methods=['POST'])
def unfollow(user_id):
    if 'user' not in session:
        flash('You must be logged in to unfollow users', 'warning')
        return redirect(url_for('login'))
    follower = User.query.filter_by(username=session['user']).first()
    followed = User.query.get_or_404(user_id)
    follow = Follows.query.filter_by(follower_id=follower.id, followed_id=followed.id).first()
    if follow:
        db.session.delete(follow)
        db.session.commit()
        flash(f'You have unfollowed {followed.username}.', 'info')
    else:
        flash('You are not following this user.', 'warning')
    return redirect(url_for('dashboard_user', username=followed.username))

@app.route('/account')
def account():
    if 'user' not in session:
        flash('You must be logged in to access your account', 'warning')
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session['user']).first()
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('dashboard'))
    earned_badges = {b.badge.name for b in user.badges}  
    all_badges = Badge.query.order_by(Badge.badge_type != 'program', Badge.badge_type != 'upvote', Badge.badge_type, Badge.required_count).all()
    return render_template('account.html', user=user, earned_badges=earned_badges, all_badges=all_badges)

@app.route('/change_email', methods=['POST'])
def change_email():
    if 'user' not in session:
        flash('You must be logged in to change your email', 'warning')
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session['user']).first()
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('dashboard'))
    new_email = request.form.get('new_email', '').strip()
    confirm_password = request.form.get('confirm_password', '')
    if not new_email or not confirm_password:
        flash('Please fill out all fields.', 'warning')
        return redirect(url_for('account'))
    if User.query.filter_by(email=new_email).first():
        flash('This email is already registered.', 'danger')
        return redirect(url_for('account'))
    if not check_password_hash(user.password_hash, confirm_password):
        flash('Incorrect password.', 'danger')
        return redirect(url_for('account'))
    user.email = new_email
    db.session.commit()
    flash('Email updated successfully!', 'success')
    return redirect(url_for('account'))

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user' not in session:
        flash('You must be logged in to change your password', 'warning')
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['user']).first()
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('dashboard'))
    
    old_password = request.form.get('old_password', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_new_password', '').strip()
    
    if not all([old_password, new_password, confirm_password]):
        flash('Please fill out all fields.', 'warning')
        return redirect(url_for('account'))
        
    if not check_password_hash(user.password_hash, old_password):
        flash('Incorrect current password.', 'danger')
        return redirect(url_for('account'))
        
    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('account'))
        
    if len(new_password) < 8:
        flash('Password must be at least 8 characters long.', 'danger')
        return redirect(url_for('account'))
    
    from werkzeug.security import generate_password_hash
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    
    flash('Password updated successfully!', 'success')
    return redirect(url_for('account'))

@app.route('/set_password', methods=['POST'])
def set_password():
    if 'user' not in session:
        flash('You must be logged in to set your password', 'warning')
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['user']).first()
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('dashboard'))
    
    if user.password_hash:
        flash('You already have a password set. Use "Change Password" instead.', 'warning')
        return redirect(url_for('account'))
    
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_new_password', '').strip()
    
    if not all([new_password, confirm_password]):
        flash('Please fill out all fields.', 'warning')
        return redirect(url_for('account'))
        
    if new_password != confirm_password:
        flash('Passwords do not match.', 'danger')
        return redirect(url_for('account'))
        
    if len(new_password) < 8:
        flash('Password must be at least 8 characters long.', 'danger')
        return redirect(url_for('account'))
    
    from werkzeug.security import generate_password_hash
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    
    flash('Password set successfully! You can now login with your username and password.', 'success')
    return redirect(url_for('account'))
   

def ai_filter_comment(content):

    bad_words = ['spam', 'badword']
    for word in bad_words:
        if word in content.lower():
            return True
    return False


# studio stuff
@app.route('/studios/<int:studio_id>/comment', methods=['POST'])
def post_studio_comment(studio_id):
    user = User.query.filter_by(username=session.get('user')).first()
    if not user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'You must be logged in to comment.'}), 401
        flash('You must be logged in to comment.', 'warning')
        return redirect(url_for('auth.login'))
    
    studio = db.session.get(Studio, studio_id)
    if not studio:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Studio not found.'}), 404
        abort(404)
    
    content = request.form.get('content', '').strip()
    parent_id = request.form.get('parent_id')
    

    if not content:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Comment cannot be empty.'}), 400
        flash('Comment cannot be empty.', 'warning')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))
    
    status = 'active'
    if ai_filter_comment(content):
        status = 'flagged'
    
    try:
        parent_id = int(parent_id) if parent_id else None
    except (TypeError, ValueError):
        parent_id = None
    comment = StudioComment(studio_id=studio_id, user_id=user.id, content=content, status=status, parent_id=parent_id)
    db.session.add(comment)
    db.session.commit()
    if studio.owner_id and user and studio.owner_id != user.id:
        owner = User.query.get(studio.owner_id)
        if owner:
            create_notification(
                user_id=owner.id,
                notif_type='studio_activity',
                message=f"{user.username} commented on your studio <span class='studio-pill'>{studio.title}</span>: &quot;{content}&quot; ",
                related_url=url_for('studio_detail', studio_id=studio.id, tab='comments')
            )
    comment.user = user
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from flask import render_template
        studio_role = get_studio_role(user.id, studio_id) if user else None
        
        if parent_id:
    
            comment_html = render_template(
                'partials/_studio_comment.html',
                comment=comment,
                current_user=user,
                studio=studio,
                studio_role=studio_role,
                is_reply=True
            )
        else:
            comment_html = render_template(
                'partials/_studio_comment.html',
                comment=comment,
                current_user=user,
                studio=studio,
                studio_role=studio_role
            )
        return jsonify({'success': True, 'comment_html': comment_html})
    if status == 'flagged':
        flash('Comment flagged for moderation.', 'warning')
    else:
        flash('Comment posted!', 'success')
    return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))


@app.route('/studios/<int:studio_id>/comment/<int:comment_id>/vote', methods=['POST'])
def vote_studio_comment(studio_id, comment_id):
    from models import StudioComment, StudioCommentVote, User
    comment = StudioComment.query.filter_by(id=comment_id, studio_id=studio_id).first_or_404()
    data = request.get_json()
    vote_type = data.get('vote')
    if vote_type not in ['up', 'down']:
        return jsonify({'error': 'Invalid vote type'}), 400

    username = session.get('user')
    if not username:
        return jsonify({'error': 'Not logged in'}), 401
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    user_id = user.id

    existing_vote = StudioCommentVote.query.filter_by(user_id=user_id, comment_id=comment_id).first()
    changed = False

    if existing_vote:
        if existing_vote.vote_type == vote_type:
            if vote_type == 'up':
                comment.upvotes = max((comment.upvotes or 0) - 1, 0)
            else:
                comment.downvotes = max((comment.downvotes or 0) - 1, 0)
            db.session.delete(existing_vote)
            changed = True
            user_vote = None
        else:
            if vote_type == 'up':
                comment.upvotes = (comment.upvotes or 0) + 1
                comment.downvotes = max((comment.downvotes or 0) - 1, 0)
            else:
                comment.downvotes = (comment.downvotes or 0) + 1
                comment.upvotes = max((comment.upvotes or 0) - 1, 0)
            existing_vote.vote_type = vote_type
            changed = True
            user_vote = vote_type
    else:
        new_vote = StudioCommentVote(user_id=user_id, comment_id=comment_id, vote_type=vote_type)
        db.session.add(new_vote)
        if vote_type == 'up':
            comment.upvotes = (comment.upvotes or 0) + 1
        else:
            comment.downvotes = (comment.downvotes or 0) + 1
        changed = True
        user_vote = vote_type

    if changed:
        db.session.commit()

    return jsonify({'upvotes': comment.upvotes, 'downvotes': comment.downvotes, 'user_vote': user_vote})

    # user = User.query.filter_by(username=session.get('user')).first()
    # studio = studio = db.session.get(Studio, studio_id)
    # if not studio:
    #     abort(404)
    # content = request.form.get('content', '').strip()
    # if not content:
    #     flash('Comment cannot be empty.', 'warning')
    #     return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))
    # status = 'active'
    # if ai_filter_comment(content):
    #     status = 'flagged'
    # comment = StudioComment(studio_id=studio_id, user_id=user.id, content=content, status=status)
    # db.session.add(comment)
    # db.session.commit()
    # if status == 'flagged':
    #     flash('Comment flagged for moderation.', 'warning')
    # else:
    #     flash('Comment posted!', 'success')
    # return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))

@app.route('/studios/<int:studio_id>/delete_comment/<int:comment_id>', methods=['POST'])
def delete_studio_comment(studio_id, comment_id):
    user = User.query.filter_by(username=session.get('user')).first()
    studio = db.session.get(Studio, studio_id)
    if not studio:
        abort(404)
    role = get_studio_role(user.id, studio_id)
    comment = StudioComment.query.get_or_404(comment_id)
    if role not in ['creator', 'manager']:
        flash('Only managers or the creator can delete comments.', 'danger')
        return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))
    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted.', 'info')
    return redirect(url_for('studio_detail', studio_id=studio_id, tab='comments'))


@app.route('/program/<int:program_id>')
def program_detail(program_id):
    program = Program.query.get_or_404(program_id)

    from models import ProgramView
    username = session.get('user')
    viewer = User.query.filter_by(username=username).first() if username else None
    if viewer:
        existing_view = ProgramView.query.filter_by(user_id=viewer.id, program_id=program.id).first()
        if not existing_view:
            new_view = ProgramView(user_id=viewer.id, program_id=program.id)
            db.session.add(new_view)
            program.views = (program.views or 0) + 1
            db.session.commit()
            unique_view = True

    username = session.get('user')
    user_vote = None
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            vote = ProgramVote.query.filter_by(user_id=user.id, program_id=program_id).first()
            if vote:
                user_vote = vote.vote_type

    comments = ProgramComment.query.filter_by(program_id=program_id).order_by(ProgramComment.created_at.asc()).all()
    comment_objs = [{'user': User.query.get(c.user_id).username if User.query.get(c.user_id) else 'Anonymous', 'text': c.content} for c in comments]
    return render_template('program_detail.html', program=program, username=username, user_vote=user_vote, comments=comment_objs)

@app.route('/program/save', methods=['POST'])
def save_program():
    name = request.form['name']
    # Prevent duplicate program names
    if Program.query.filter_by(name=name).first():
        return "A program with this name already exists. Please choose a different name.", 400
    description = request.form['description']
    controls = request.form['controls']
    image_url = request.form.get('image_url', '')
    image_file = request.files.get('image')
    developer = request.form['developer']
    version = request.form['version']
    mod_perms = request.form['mod_perms']
    last_updated = datetime.now()
    program_url = request.form["program_url"]
    print(program_url)
  
    # Generate a unique 10-digit id
    while True:
        random_id = random.randint(10**9, 10**10-1)
        if not Program.query.get(random_id):
            break
    print(random_id)
    program = Program(
        id=random_id,
        name=name,
        description=description,
        controls=controls,
        image_url=image_url,
        developer=developer,
        version=version,
        last_updated=last_updated,
        mod_perms=mod_perms,
        program_url=program_url
    )
    print("Saving program_url:", program_url)
    db.session.add(program)
    db.session.commit()

    username = session.get('user')
    user = User.query.filter_by(username=username).first() if username else None
    if image_file and image_file.filename and user:
        supa_url = upload_image_to_supabase(image_file, folder=f'{user.username}/program_thumbnails')
        if supa_url:
            program.image_url = supa_url
            db.session.commit()

    if 'user' in session:
        user = User.query.filter_by(username=session['user']).first()
        if user:
            activity = Activity(user_id=user.id, activity_date=date.today())
            db.session.add(activity)
            db.session.commit()
    flash('Program created successfully!', 'success')
    return redirect(url_for('programs'))

@app.route('/program/<int:program_id>/edit', methods=['GET', 'POST'])
def edit_program(program_id):
    program = Program.query.get_or_404(program_id)
    if request.method == 'POST':
        program.name = request.form['name']
        program.description = request.form['description']
        program.controls = request.form['controls']
        image_file = request.files.get('image')
        program.last_updated = datetime.now()
        
        if 'developer' in request.form and request.form['developer']:
            program.developer = request.form['developer']
        if 'version' in request.form and request.form['version']:
            program.version = request.form['version']
        if 'program_url' in request.form:
            program.program_url = request.form['program_url']
        
        username = session.get('user')
        user = User.query.filter_by(username=username).first() if username else None
        if image_file and image_file.filename and user and allowed_file(image_file.filename):
            from supabase_utils import delete_image_from_supabase, upload_image_to_supabase

            if program.image_url:
                try:
                    delete_image_from_supabase(program.image_url)
                except Exception as e:
                    app.logger.error(f"Error deleting old image: {str(e)}")

            try:
                supa_url = upload_image_to_supabase(image_file, folder=f'{user.username}/program_thumbnails')
                if supa_url:
                    program.image_url = supa_url
                    flash('Image uploaded successfully!', 'success')
            except Exception as e:
                app.logger.error(f"Error uploading new image: {str(e)}")
                flash('Error uploading image. Please try again.', 'error')
        
        db.session.commit()
        
     
        if 'user' in session:
            user = User.query.filter_by(username=session['user']).first()
            if user:
                activity = Activity(user_id=user.id, activity_date=date.today())
                db.session.add(activity)
                db.session.commit()
                
        flash('Program updated successfully!', 'success')
        return redirect(url_for('program_detail', program_id=program.id))
    return render_template('edit_program.html', program=program)

@app.route('/program/<int:program_id>/delete', methods=['POST'])
def delete_program(program_id):
    if 'user' not in session:
        flash('Please log in to delete programs.', 'error')
        return redirect(url_for('login'))
    
    program = Program.query.get_or_404(program_id)
    username = session.get('user')
    user = User.query.filter_by(username=username).first() if username else None

    if not user or program.developer != user.username:
        flash('You do not have permission to delete this program.', 'error')
        return redirect(url_for('myprograms'))

    try:
        StudioProject.query.filter_by(program_id=program_id).delete()
    except Exception as e:
        pass

    try:
 
        from models import ProgramView, UserProgramTier
        ProgramView.query.filter_by(program_id=program_id).delete()
        UserProgramTier.query.filter_by(program_id=program_id).delete()
        
        StudioActivity.query.filter_by(project_id=program_id).delete()

        ProgramComment.query.filter_by(program_id=program_id).delete()
        ProgramVote.query.filter_by(program_id=program_id).delete()

        
        if program.image_url:
            try:
                from supabase_utils import delete_image_from_supabase
                delete_image_from_supabase(program.image_url)
            except Exception as e:
                app.logger.error(f"Error deleting image from storage: {str(e)}")
        

        activity = Activity(user_id=user.id, activity_date=date.today())
        db.session.add(activity)
        

        db.session.delete(program)
        db.session.commit()
    
        flash('Program deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting program: {str(e)}", exc_info=True)
        flash('An error occurred while deleting the program.', 'error')
    
    return redirect(url_for('myprograms'))

@app.route('/log')
def log():
    if 'user' not in session:
        flash('Please log in to view the log.', 'warning')
        return redirect(url_for('login', next='log'))
    return render_template('log.html') 

import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/new_project', methods=['GET', 'POST'])
def new_project():
    if 'user' not in session:
        flash('You must be logged in', 'warning')
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        controls = request.form['controls']
        program_url = request.form['program_url']

        # if 'arcade.makecode.com' in program_url:
        #     if not program_url.startswith(('http://', 'https://')):
        #         program_url = f'https://{program_url}'
        #     if not any(x in program_url for x in ['/S', '/s']):
        #         flash('Invalid MakeCode Arcade share link format', 'danger')
        #         return redirect(url_for('new_project'))
                
        image = request.files.get('image')
        from supabase_utils import upload_image_to_supabase
        if image and allowed_file(image.filename):
            username = session.get('user')

            user = User.query.filter_by(username=username).first() if username else None
            if user:
                image_url = upload_image_to_supabase(image, folder=f'{user.username}/program_thumbnails')
            else:
                image_url = None
        else:
            image_url = None    
        # session['program_preview'] = {
        #     'name': name,
        #     'description': description,
        #     'controls': controls,
        #     'image_url': image_url,
        #     'developer': session.get('user', 'Unknown'),
        #     'version': '1.0.0',
        #     'mod_perms': '',
        #     'program_url': program_url
        # }
        # return redirect(url_for('program_preview'))

        pdt = pytz.timezone('America/Los_Angeles')
        now_pdt = datetime.now(pdt)

        max_attempts = 100
        for _ in range(max_attempts):
            program_id = random.randint(10000000, 99999999)
            if not Program.query.get(program_id):
                break
        else:
            last_id = db.session.query(db.func.max(Program.id)).scalar() or 10000000
            program_id = last_id + 1
        
        program = Program(
            id=program_id,
            name=name,
            description=description,
            controls=controls,
            image_url=image_url,
            developer=session.get('user', 'Unknown'),
            version='1.0.0',
            mod_perms='',
            program_url=program_url,
            last_updated=now_pdt,
            likes=0,
            dislikes=0
        )
        db.session.add(program)
        db.session.commit()
        
        flash('Program created successfully!', 'success')
        return redirect(url_for('program_detail', program_id=program.id))
    return render_template('new_project.html')

@app.route('/program/preview')

def program_preview():
    data = session.get('program_preview')
    if not data:
        flash('No program data found.', 'warning')
        return redirect(url_for('new_project'))
    return render_template('program_preview.html', **data)


@app.route('/dashboard/save_tiers', methods=['POST'])

def save_tiers():
    username = session.get('user')
    user = User.query.filter_by(username=username).first()
    data = request.get_json()
    print('Saving tiers for user', user.id, data)
    if not data:
        return {'success': False, 'error': 'No data provided'}, 400
    for tier, ids in data.items():
        for pid in ids:
            upt = UserProgramTier.query.filter_by(user_id=user.id, program_id=int(pid)).first()
            if upt:
                upt.tier = tier
            else:
                db.session.add(UserProgramTier(user_id=user.id, program_id=int(pid), tier=tier))
    db.session.commit()
    return {'success': True}

def get_programs_with_tier(user_id):
    from models import Program, UserProgramTier
    programs = Program.query.filter_by(developer=User.query.get(user_id).username).all()
    result = []
    for p in programs:
        upt = UserProgramTier.query.filter_by(user_id=user_id, program_id=p.id).first()
        result.append({
            'id': p.id,
            'name': p.name,
            'image_url': p.image_url,
            'tier': upt.tier if upt else 'N/A'
        })
    return result



@app.route('/dashboard')
def dashboard():
    if not session.get('user'):
        flash('You must be logged in to view the dashboard.', 'warning')
        return redirect(url_for('login'))
    from calendar import monthrange
   

    username = session.get('user')
    user = User.query.filter_by(username=username).first()

    makejam_data = None
    makejam_submissions = None
    makejams_ongoing = []

    if username == 'MakeJam':
        today = date.today()
        db.session.expire_all()

        makejams_ongoing = MakeJam.query.filter(MakeJam.start_date <= today, MakeJam.end_date >= today).order_by(MakeJam.start_date.desc()).all()
        if makejams_ongoing:
            makejam_data = makejams_ongoing[0]  
            makejam_submissions = MakeJamSubmission.query.filter_by(jam_id=makejam_data.id).all()
        else:
            most_recent_jam = MakeJam.query.order_by(MakeJam.start_date.desc()).first()
            if most_recent_jam:
                makejam_data = most_recent_jam
                makejam_submissions = MakeJamSubmission.query.filter_by(jam_id=makejam_data.id).all()
            else:
                makejam_data = None
                makejam_submissions = []
        # --- NEW: Find all jams with unscored submissions ---
        from sqlalchemy import or_
        all_jams = MakeJam.query.order_by(MakeJam.start_date.desc()).all()
        jams_with_submissions = []
        for jam in all_jams:
            unscored_subs = [sub for sub in jam.submissions if (sub.total_score is None or sub.total_score == 0)]
            if unscored_subs:
                jams_with_submissions.append({'jam': jam, 'submissions': unscored_subs})
    else:
        jams_with_submissions = None

    activities = Activity.query.filter_by(user_id=user.id).order_by(Activity.activity_date).all()
    days = {}
    for a in activities:
        days[a.activity_date] = days.get(a.activity_date, 0) + 1
    today = date.today()

    num_months = 12

    months = []
    month_blocks = []
    current = today.replace(day=1)
    for _ in range(num_months):
        months.append(current)
        current = (current.replace(day=1) - timedelta(days=1)).replace(day=1)
    months = months[::-1]
    for m in months:
        days_in_month = monthrange(m.year, m.month)[1]
        block = [days.get(m.replace(day=day), 0) for day in range(1, days_in_month+1)]
        month_blocks.append({'month': m.month, 'year': m.year, 'days': block})
    total_active_days = sum(days.values())
    programs_with_tier = get_programs_with_tier(user.id)

    profile_pic_url = user.profile_pic_url or url_for('static', filename='img/default_avatar.svg')

    user_programs = Program.query.filter_by(developer=username).all()
    upvotes = sum(p.likes or 0 for p in user_programs)
    downvotes = sum(p.dislikes or 0 for p in user_programs)

    comment_count = 0
    for p in user_programs:
        comment_count += ProgramComment.query.filter_by(program_id=p.id).count()
    # Profile info
    profile_pic_url = getattr(user, 'profile_pic_url', '/static/themes/makecore/img/default_avatar.svg')
    viewing_user_profile_pic_url = getattr(user, 'profile_pic_url', '/static/themes/makecore/img/default_avatar.svg')
    bio = user.bio
    rank = getattr(user, 'rank', 'Member')
    user_dict = {
        'username': user.username,
        'profile_pic_url': profile_pic_url,
        "viewing_user_profile_pic_url": viewing_user_profile_pic_url,
        'bio': bio,
        'rank': rank,
        'upvotes': upvotes,
        'downvotes': downvotes,
        'comments': comment_count,
        'views': sum(p.views or 0 for p in user_programs),
    }

    followers = []
    for f in user.followers:
        follower_user = User.query.get(f.follower_id)
        if follower_user:
            followers.append({
                'username': follower_user.username,
                'profile_pic_url': follower_user.profile_pic_url or '/static/themes/makecore/img/default_avatar.svg',
                'is_followed': True, 
                'location': getattr(follower_user, 'location', '')
            })

    followers_query = Follows.query.filter_by(followed_id=user.id).all()
    follower_count = len(followers_query)
    
    following_query = Follows.query.filter_by(follower_id=user.id if hasattr(user, 'id') else user.get('id')).all()
    following_count = len(following_query)

    earned_badge_ids = {b.badge_id for b in User.query.filter_by(username=username).first().badges}
    earned_badges = [{
        'id': badge.id,
        'name': badge.name,
        'description': badge.description,
        'icon_url': badge.icon_url,
        'tooltip': badge.tooltip,
        'badge_type': badge.badge_type,
        'required_count': badge.required_count,
        'earned': badge.id in earned_badge_ids
    } for badge in Badge.query.filter(Badge.id.in_(earned_badge_ids)).all()] if earned_badge_ids else []


    return render_template(
        'dashboard.html',
        username=username,
        month_blocks=month_blocks,
        total_active_days=total_active_days,
        programs=programs_with_tier,
        user=user_dict,
        followers=followers,
        makejam=makejam_data,
        makejam_submissions=makejam_submissions,
        jams_with_unscored=jams_with_submissions,
        makejam_rating=getattr(user, 'rating', None),
        session_user=user,
        userData=user,
        follower=follower_count,
        following=following_count,
        earned_badges=earned_badges,
        badge_username=user.username,
    )

@app.route('/dashboard/<username>')
def dashboard_user(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('dashboard'))
    
    
    makejam_rating = getattr(user, 'rating', None)
    print("MAKEJAM RATING" + str(makejam_rating) + str(username))
    from calendar import monthrange
    account_user = user
    is_following = False
    session_user = None
    if 'user' in session:
        session_user = User.query.filter_by(username=session['user']).first()
        if session_user and session_user.id != user.id:
            is_following = Follows.query.filter_by(follower_id=session_user.id, followed_id=user.id).first() is not None
    activities = Activity.query.filter_by(user_id=user.id).order_by(Activity.activity_date).all()
    days = {}
    for a in activities:
        days[a.activity_date] = days.get(a.activity_date, 0) + 1
    today = date.today()
    num_months = 12
    months = []
    month_blocks = []
    current = today.replace(day=1)
    for _ in range(num_months):
        months.append(current)
        prev_month = current.month - 1 or 12
        prev_year = current.year - 1 if current.month == 1 else current.year
        current = current.replace(year=prev_year, month=prev_month)
    months = months[::-1]
    for m in months:
        _, days_in_month = monthrange(m.year, m.month)
        block = [days.get(date(m.year, m.month, d+1), 0) for d in range(days_in_month)]
        month_blocks.append({'month': m.strftime('%b %Y'), 'days': block})
    total_active_days = len(days)

    programs = Program.query.filter_by(developer=username).all()
    programs_with_tier = []
    for p in programs:
        upt = UserProgramTier.query.filter_by(user_id=user.id, program_id=p.id).first()
        programs_with_tier.append({
            'id': p.id,
            'name': p.name,
            'image_url': p.image_url,
            'tier': upt.tier if upt else None
        })
    upvotes = sum([p.likes or 0 for p in programs])
    downvotes = sum([p.dislikes or 0 for p in programs])
    comment_count = 0 # total comments received on all their programs combined
    for p in programs:
        comment_count += ProgramComment.query.filter_by(program_id=p.id).count()

    profile_pic_url = session_user.profile_pic_url if session_user else None
    viewing_user_profile_pic_url = user.profile_pic_url
    
    bio = getattr(user, 'bio', 'No bio set.')
    rank = getattr(user, 'rank', 'Member')
    
    user_dict = {
        'username': session_user.username if session_user else None,
        'is_logged_in': session_user is not None,
        'profile_pic_url': profile_pic_url,
        'viewing_user_profile_pic_url': viewing_user_profile_pic_url,
        'bio': bio,
        'rank': rank,
        'upvotes': upvotes,
        'downvotes': downvotes,
        'comments': comment_count,
        "views": sum(p.views or 0 for p in programs)
    }

    followers_query = Follows.query.filter_by(followed_id=user.id).all()
    followers = []
    for f in followers_query:
        follower_user = User.query.get(f.follower_id)
        if follower_user:
            followers.append({
                'username': follower_user.username,
                'profile_pic_url': getattr(follower_user, 'profile_pic_url', None)
            })

    follower_count = len(followers_query)
    
    following_query = Follows.query.filter_by(follower_id=user.id if hasattr(user, 'id') else user.get('id')).all()
    following_count = len(following_query)

    earned_badge_ids = {b.badge_id for b in User.query.filter_by(username=username).first().badges}
    earned_badges = [{
        'id': badge.id,
        'name': badge.name,
        'description': badge.description,
        'icon_url': badge.icon_url,
        'tooltip': badge.tooltip,
        'badge_type': badge.badge_type,
        'required_count': badge.required_count,
        'earned': badge.id in earned_badge_ids
    } for badge in Badge.query.filter(Badge.id.in_(earned_badge_ids)).all()] if earned_badge_ids else []

    return render_template(
        'dashboard.html',
        username=user.username,
        month_blocks=month_blocks,
        total_active_days=total_active_days,
        programs=programs_with_tier,
        user=user_dict,
        account_user=account_user,
        is_following=is_following,
        makejam_rating=makejam_rating,
        followers=followers,
        userData=user,
        session_user=session_user,
        following=following_count,
        follower=follower_count,
        earned_badges=earned_badges,
        badge_username=username
    )

@app.route('/edit_profile', methods=['POST'])
def edit_profile():
    if 'user' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'You must be logged in to edit your profile'}), 401
        flash('You must be logged in to edit your profile', 'warning')
        return redirect(url_for('login'))
        
    user = User.query.filter_by(username=session['user']).first()
    if not user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'User not found'}), 404
        flash('User not found.', 'danger')
        return redirect(url_for('dashboard'))

    # Handle avatar upload
    if 'profile_pic' in request.files and request.files['profile_pic'].filename:
        try:
            file = request.files['profile_pic']
            if user.profile_pic_url:
                from supabase_utils import delete_image_from_supabase
                delete_image_from_supabase(user.profile_pic_url)
            
            supa_url = upload_image_to_supabase(file, folder=f'{user.username}/profile')
            if supa_url:
                user.profile_pic_url = supa_url
                db.session.commit()
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': True,
                        'profile_pic_url': supa_url,
                        'message': 'Profile picture updated successfully!'
                    })
                flash('Profile picture updated successfully!', 'success')
            else:
                raise Exception('Failed to upload image to storage')
                
        except Exception as e:
            print(f"Error updating profile picture: {str(e)}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'error': 'Failed to update profile picture. Please try again.'
                }), 500
            flash('Failed to update profile picture.', 'danger')
    
    # Handle bio update if it's a regular form submission
    if 'bio' in request.form:
        bio = request.form.get('bio', '').strip()
        user.bio = bio
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': 'Profile updated successfully!'
            })
        flash('Profile updated successfully!', 'success')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': False, 'error': 'No valid updates provided'}), 400
    
    return redirect(url_for('dashboard'))

@app.route('/myprograms')
def myprograms():
    username = session.get('user')
    if not username:
        return redirect(url_for('login'))
    
    # Get user's programs
    programs = Program.query.filter_by(developer=username).order_by(Program.last_updated.desc()).all()
    comments = {}
    for p in programs:
        comments[p] = ProgramComment.query.filter_by(program_id=p.id).count()
    
    # Get user's owned studios
    user = User.query.filter_by(username=username).first()
    owned_studios = Studio.query.filter_by(owner_id=user.id).order_by(Studio.created_at.desc()).all()
    
    return render_template('myprograms.html', programs=programs, comments=comments, owned_studios=owned_studios)

@app.route('/notifications')
def notifications():
    return render_template('notifications.html')


from utils.jam_utils import calculate_rating_changes
@app.route('/makejam/<int:jam_id>/finalize_ratings', methods=['POST'])
def finalize_jam_ratings(jam_id):
    username = session.get('user')
    
    if username != 'MakeJam':
        return jsonify({'error': 'Access denied'}), 403
    ok = calculate_rating_changes(jam_id)
    if ok:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'No scores found'})

@app.route('/makejam/submission/<int:submission_id>/rate', methods=['POST'])
def makejam_rate_submission(submission_id):
    from models import SubmissionScore
    username = session.get('user')
    if username != 'MakeJam':
        return jsonify({'error': 'Access denied'}), 403

    submission = MakeJamSubmission.query.get_or_404(submission_id)
 
    rubric_fields = [
        'theme_use', 'theme_build', 'art_style', 'art_originality',
        'enjoyment', 'learning_curve', 'gameplay_loop', 'concept', 'creative_theme'
    ]
    for field in rubric_fields:
        value = request.form.get(field, type=int)
        setattr(submission, field, value)
    db.session.commit()


    score_obj = SubmissionScore.query.filter_by(user_id=submission.user_id, jam_id=submission.jam_id).first()
    if not score_obj:
        score_obj = SubmissionScore(user_id=submission.user_id, jam_id=submission.jam_id, score=submission.total_score)
        db.session.add(score_obj)
    else:
        score_obj.score = submission.total_score
    db.session.commit()


    jam = submission.jam

    pdt = pytz.timezone('America/Los_Angeles')
    now_pdt = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(pdt)
    all_graded = all(s.total_score is not None for s in jam.submissions)
    if all_graded and not jam.ratings_finalized:
        from utils.rating_calculator import calculate_rating_changes
        calculate_rating_changes(jam.id)
        print("Ratings Finalized!")
        jam.ratings_finalized = True
        jam.ratings_finalized_at = now_pdt
        db.session.commit()

    return jsonify({'success': True, 'total_score': submission.total_score})

@app.route('/api/jam_status/<int:jam_id>')
def api_jam_status(jam_id):
    import pytz
    from datetime import datetime
    jam = MakeJam.query.get_or_404(jam_id)
    pdt = pytz.timezone('America/Los_Angeles')
    now_pdt = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(pdt)
    jam_end = jam.end_date.astimezone(pdt) if jam.end_date.tzinfo else jam.end_date.replace(tzinfo=pytz.utc).astimezone(pdt)
    status = "Ongoing" if jam_end > now_pdt else "Closed"
    seconds_left = max(0, int((jam_end - now_pdt).total_seconds()))
    return jsonify({
        "status": status,
        "seconds_left": seconds_left,
        "now_pdt": now_pdt.strftime("%Y-%m-%d %H:%M:%S"),
        "jam_end": jam_end.strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route('/makejams')
def makejam_list():
    jams = MakeJam.query.order_by(MakeJam.id.desc()).all()  
    username = session.get('user')
    user = User.query.filter_by(username=username).first() if username else None
    participated_jam_ids = []
    participated_jams = []
    if user:
        from models import MakeJamSubmission
        participated_jam_ids = [s.jam_id for s in MakeJamSubmission.query.filter_by(user_id=user.id).all()]
        participated_jams = [jam for jam in jams if jam.id in participated_jam_ids]
    
    utc = pytz.utc
    pdt = pytz.timezone('America/Los_Angeles')
    now_utc = datetime.utcnow().replace(tzinfo=utc)
    now_pdt = now_utc.astimezone(pdt)
  
    active_jams = []
    past_jams = jams.copy()
    if jams:
        utc = pytz.utc
        pdt = pytz.timezone('America/Los_Angeles')
        now_utc = datetime.utcnow().replace(tzinfo=utc)
        now_pdt = now_utc.astimezone(pdt)
        newest_jam_end = jams[0].end_date.replace(tzinfo=utc).astimezone(pdt) if jams[0].end_date.tzinfo is None else jams[0].end_date.astimezone(pdt)
        if newest_jam_end > now_pdt:
            active_jams = [jams[0]]
            past_jams = jams[1:] if len(jams) > 1 else []
    can_submit_project = False
    if active_jams and user:
        user_ids = [s.user_id for s in getattr(active_jams[0], 'submissions', [])]
        can_submit_project = user.id not in user_ids


    leaderboard_users = User.query.order_by(User.rating.desc()).limit(10).all()

    minutes_remaining = None
    if active_jams:
        jam_end = active_jams[0].end_date.replace(tzinfo=utc).astimezone(pdt) if active_jams[0].end_date.tzinfo is None else active_jams[0].end_date.astimezone(pdt)
        delta = jam_end - now_pdt
        minutes_remaining = int(delta.total_seconds() // 60)
    no_active_jam = not active_jams
    return render_template('makejam_list.html', active_jams=active_jams, past_jams=past_jams, participated_jams=participated_jams, user=user, can_submit_project=can_submit_project, leaderboard_users=leaderboard_users, minutes_remaining=minutes_remaining, now_pdt=now_pdt, no_active_jam=no_active_jam)



@app.route('/makejams/<int:jam_id>', methods=['GET', 'POST'])
def makejam_detail(jam_id):
    import pytz
    jam = MakeJam.query.get_or_404(jam_id)
    username = session.get('user')
    user = User.query.filter_by(username=username).first() if username else None
    user_submission = None
    if user:
        user_submission = MakeJamSubmission.query.filter_by(jam_id=jam.id, user_id=user.id).first()
    if request.method == 'POST':
        if not user:
            flash('You must be logged in to submit a project', 'warning')
            return redirect(url_for('login'))
        title = request.form.get('project_title', '').strip()
        link = request.form.get('project_link', '').strip()
        desc = request.form.get('description', '').strip()
        if title and link:
            if user_submission:
                user_submission.project_title = title
                user_submission.project_link = link
                user_submission.description = desc
            else:
                submission = MakeJamSubmission(
                    jam_id=jam.id, user_id=user.id,
                    project_title=title, project_link=link, description=desc
                )
                db.session.add(submission)
                flash('Project submitted!', 'success')
            db.session.commit()
            return redirect(url_for('makejam_detail', jam_id=jam.id))
    submissions = MakeJamSubmission.query.filter_by(jam_id=jam.id).all()
    utc = pytz.utc
    pdt = pytz.timezone('America/Los_Angeles')
    now_utc = datetime.utcnow().replace(tzinfo=utc)
    now_pdt = now_utc.astimezone(pdt)
    jam_start = to_pdt(jam.start_date)
    jam_end = to_pdt(jam.end_date)
    return render_template('makejam_detail.html', jam=jam, submissions=submissions, user_submission=user_submission, user=user, now_pdt=now_pdt, jam_start_pdt=jam_start, jam_end_pdt=jam_end)


def to_pdt(dt):
    import pytz
    pdt = pytz.timezone('America/Los_Angeles')
    utc = pytz.utc
    if dt.tzinfo:
        return dt.astimezone(pdt)
    else:
        return dt.replace(tzinfo=utc).astimezone(pdt)


@app.route('/makejams/new', methods=['GET', 'POST'])
def makejam_new():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        desc = request.form.get('description', '').strip()
        start = request.form.get('start_date', '').strip()
        start_time = request.form.get('start_time', '').strip()
        end = request.form.get('end_date', '').strip()
        end_time = request.form.get('end_time', '').strip()
        admin_password = request.form.get('admin_password', '')
        expected_password = os.getenv('MAKEJAM_ADMIN_PASSWORD', '')
        form_data = {
            'name': name,
            'description': desc,
            'start_date': start,
            'start_time': start_time,
            'end_date': end,
            'end_time': end_time
        }
        if admin_password != expected_password:
            flash('Incorrect admin password.', 'danger')
            return render_template('makejam_new.html', form_data=form_data)
        elif not name or not start or not start_time or not end or not end_time:
            flash('Name, start date/time, and end date/time are required.', 'danger')
            return render_template('makejam_new.html', form_data=form_data)
        else:
            try:
                pdt = pytz.timezone('America/Los_Angeles')

                start_naive = datetime.strptime(f'{start} {start_time}', '%Y-%m-%d %H:%M')
                end_naive = datetime.strptime(f'{end} {end_time}', '%Y-%m-%d %H:%M')
                start_pdt = pdt.localize(start_naive)
                end_pdt = pdt.localize(end_naive)
                start_dt = start_pdt.astimezone(pytz.utc)
                end_dt = end_pdt.astimezone(pytz.utc)
                thumbnail_file = request.files.get('thumbnail')
                thumbnail_url = None
                if thumbnail_file and thumbnail_file.filename:
                    from supabase_utils import upload_image_to_supabase
                    thumbnail_url = upload_image_to_supabase(thumbnail_file, folder='makejam')
                # ---
                jam = MakeJam(
                    name=name, description=desc,
                    start_date=start_dt, end_date=end_dt, status='upcoming',
                    thumbnail=thumbnail_url if thumbnail_url else None
                ) if 'thumbnail' in MakeJam.__table__.columns else MakeJam(
                    name=name, description=desc,
                    start_date=start_dt, end_date=end_dt, status='upcoming'
                )
                db.session.add(jam)
                db.session.commit()
                flash('MakeJam created!', 'success')
                return redirect(url_for('makejam_list'))
            except Exception as e:
                flash('Invalid date format.', 'danger')
                return render_template('makejam_new.html', form_data=form_data)
    return render_template('makejam_new.html')

# MakeJams rating ranking calculation
def get_user_rank(user_id, jam_id):
    submissions = MakeJamSubmission.query.filter_by(jam_id=jam_id).all()
    sorted_submissions = sorted(submissions, key=lambda x: x.rating_after, reverse=True)
    for i, sub in enumerate(sorted_submissions, 1):
        if sub.user_id == user_id:
            return i
    return 0 # user not found in this jam

def get_global_rank(user_id):
    ranked_user = User.query.filter(User.rating.isnot(None)).order_by(User.rating.desc()).all()
    for rank, user in enumerate(ranked_user, 1):
        if user.id == user_id:
            return rank
    return 0 # no rating

def get_makejams_attended(user_id):
    count = db.session.query(db.func.count(db.func.distinct(MakeJamSubmission.jam_id))).filter(MakeJamSubmission.user_id == user_id).scalar()
    return count or 0

@app.route('/leaderboard')
def leaderboard():
    page = request.args.get('page', 1, type=int)
    per_page = 30
    
    total_users = User.query.count()
    
    leaderboard_users = User.query.order_by(User.rating.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    for user in leaderboard_users.items:
        user.contests_participated = get_makejams_attended(user.id)
    
    return render_template('leaderboard.html', 
                         leaderboard_users=leaderboard_users.items,
                         pagination=leaderboard_users,
                         current_page=page)

# -------- api -----------

@app.route("/api/user/programs")
def get_user_programs():
    try:
        username = session.get('user')
        user = User.query.filter_by(username=username).first()
        programs = Program.query.filter_by(developer=username).all()
       
        program_list = [{
            "id": program.id, 
            "name": program.name, 
            "thumbnail": program.image_url,
            "is_featured": program.is_featured,
            "url": f"/programs/{program.id}"  
        } for program in programs]
        return jsonify(program_list)
    except Exception as e:
        app.logger.error(f"Error fetching user programs: {str(e)}")
        
        return jsonify({"error": "Failed to fetch programs"}), 500

@app.route("/api/user/get_featured_program")
@app.route("/api/user/<username>/get_featured_program")
def get_featured_program(username=None):
    try:
        if username is None:
            username = session.get('user')
            if not username:
                return jsonify({"error": "Login required"}), 401
        
        program = Program.query.filter_by(
            developer=username,
            is_featured=True
        ).first()
        print("PROGRAM NAME" + program.name)
        if program:
            return jsonify({
                "program": {
                    "id": program.id,
                    "name": program.name,
                    "image_url": program.image_url,
                    "description": program.description
                }
            })
        return jsonify({"program": None})
        
    except Exception as e:
        app.logger.error(f"Error getting featured program: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@app.route("/api/user/featured_program", methods=['POST'])
def set_featured_program():
    try:
        username = session.get('user')
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        program_id = data.get("program_id")
        if not program_id:
            return jsonify({"error": "Program ID is required"}), 400
            
        Program.query.filter_by(
            developer=username,
            is_featured=True
        ).update({"is_featured": False})
        
        program = Program.query.filter_by(
            id=program_id,
            developer=username
        ).first()
        
        if not program:
            return jsonify({"error": "Program not found"}), 404
            
        program.is_featured = True
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Featured program updated successfully"
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating featured program: {str(e)}")
        return jsonify({"error": "Failed to update featured program"}), 500

@app.route('/api/user/rating_history')
@app.route('/api/user/<username>/rating_history')
def get_user_rating_history(username=None):
    if username is None:
        username = session.get('user')
        if not username:
            return jsonify({'error': 'Not logged in'}), 401
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    try:
        submissions = (
            db.session.query(MakeJamSubmission, MakeJam)
            .join(MakeJam, MakeJam.id == MakeJamSubmission.jam_id)
            .filter(
                MakeJamSubmission.user_id == user.id,
                MakeJamSubmission.rating_after.isnot(None)
            )
            .order_by(MakeJam.end_date.asc())
            .all()
        )
        
        # response data
        rating_history = []
        prev_rating = None
        global_rank = get_global_rank(user.id)
        makejams_attended = get_makejams_attended(user.id)
        
        for submission, jam in submissions:
            rating_change = 0
            if prev_rating is not None:
                rating_change = submission.rating_after - prev_rating
            prev_rating = submission.rating_after
            
            rank = get_user_rank(user.id, jam.id)
            rating_history.append({
                "date": jam.end_date.strftime('%Y-%m-%d'),
                "rating": submission.rating_after,
                "contest": jam.name,
                "rating_change": rating_change,
                "rank": rank,
                "global_rank": global_rank,
                "makejams_attended": makejams_attended
            })
        
        return jsonify(rating_history)
    
    except Exception as e:
        print(f"Error getting rating history: {str(e)}")
        return jsonify({'error': 'Failed to fetch rating history'}), 500

def add_makejam_admin():
    admin_username = 'MakeJam'
    admin_password = os.environ.get('MAKEJAM_ADMIN_PASSWORD')
    from werkzeug.security import generate_password_hash
    admin = User.query.filter_by(username=admin_username).first()
    if not admin:
        admin = User(
            username=admin_username,
            email='makejam@admin.com',
            password_hash=generate_password_hash(admin_password)
        )
        db.session.add(admin)
        db.session.commit()
        print('MakeJam admin user created!')

@app.route('/credits')
def credits():
    supporters = []
    users = User.query.with_entities(User.username, User.show_ads, User.profile_pic_url).all()
    for user in users:
        if user[1]:
            supporters.append([user[0], user[2]])

    return render_template('credits.html', supporters=supporters)

@app.route('/ads')
def ads():
    return render_template('ads.html')

@app.route('/updates')
def updates():
    return render_template('updates.html')

@app.route('/featured')
def featured():
    supporters = User.query.filter_by(show_ads=True).all()
    games = []
    profile_pics = {}
    for supporter in supporters:
        programs = Program.query.filter_by(developer=supporter.username).order_by(func.random()).all()
        length = len(programs)
        for i in range(length):
            program = programs[i]
            if "makecode" in program.program_url or "scratch" in program.program_url:
                games.append(program)
                profile_pics[program] = (supporter.profile_pic_url)
                break
            # if "scratch" in program.program_url:
            #     games.append(program)
            #     profile_pics[program] = (supporter.profile_pic_url)
            #     break

    comments = {}
    views = {}
    for game in games:
        comments[game] = ProgramComment.query.filter_by(program_id=game.id).count()
        views[game] = ProgramView.query.filter_by(program_id=game.id).count()
    random.shuffle(games)

    username = session.get('user')
    user = User.query.filter_by(username=username).first() if username else None

    
    return render_template('featured.html', games=games, user=user, comments=comments, views=views, profile_pics=profile_pics)

@app.route('/ideas')
def ideas():
    return render_template('ideas.html')


@app.route('/update_ads_toggle', methods=['POST'])
def update_ads_toggle():
    if 'user' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Not logged in'}), 401
        return redirect(url_for('login'))
        
    user = User.query.filter_by(username=session['user']).first()
    if not user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'User not found'}), 404
        return redirect(url_for('account'))
    
    try:
        show_ads = 'show_ads' in request.form
        user.show_ads = show_ads
        session['show_ads'] = show_ads  # Update session with the new value
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': 'Ads preference updated successfully!',
                'show_ads': show_ads
            })
            
        flash('Ads preference updated successfully!', 'success')
        return redirect(url_for('account'))
        
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': f'Error updating ads preference: {str(e)}'
            }), 500
        flash(f'Error updating ads preference: {str(e)}', 'error')
        return redirect(url_for('account'))

def initialize_db():
    run(f'psql "{os.getenv("DATABASE_URL")}" < init_db.sql', shell=True, check=True)

        
# Old refer to version 3.1.0
@app.route('/clear_new_badge', methods=['POST'])
def clear_new_badge():
    if 'newBadge' in session:
        session.pop('newBadge', None)
    return jsonify({'status': 'success'})

if __name__ == "__main__":
    # port = 5000
    # initialize_db()
    # for i, arg in enumerate(sys.argv):
    #     if arg == '--port' and i+1 < len(sys.argv):
    #         try:
    #             port = int(sys.argv[i+1])
    #         except Exception:
    #             pass
    app.run(host="0.0.0.0", port=5000)
