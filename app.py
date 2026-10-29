import os
import sqlite3
import base64
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, 
    flash, session
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from database import get_db, init_db, close_connection
from ai_model import VoterAIVerifier

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super-secret-production-key-change-me')
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
ai_verifier = VoterAIVerifier()

# Initialize Database Schema
with app.app_context():
    init_db(app)

app.teardown_appcontext(close_connection)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Security Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin authorization required.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        file = request.files.get('face_image')
        camera_b64 = request.form.get('camera_image', '').strip()

        if not username or not email or not password:
            flash('Username, email, and password are required.', 'error')
            return redirect(url_for('register'))

        if not file and not camera_b64:
            flash('Please either capture a live photo or upload an image file.', 'error')
            return redirect(url_for('register'))

        filepath = None

        # Case 1: Live Camera Image Captured (Base64)
        if camera_b64 and camera_b64.startswith('data:image'):
            filename = secure_filename(f"{username}_cam.jpg")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            try:
                header, encoded = camera_b64.split(',', 1)
                data = base64.b64decode(encoded)
                with open(filepath, 'wb') as f:
                    f.write(data)
            except Exception:
                flash('Error processing live camera capture.', 'error')
                return redirect(url_for('register'))

        # Case 2: Uploaded Image File
        elif file and allowed_file(file.filename):
            filename = secure_filename(f"{username}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
        else:
            flash('Invalid image format. Allowed formats: PNG, JPG, JPEG.', 'error')
            return redirect(url_for('register'))

        # AI Facial Verification
        is_valid, msg = ai_verifier.detect_and_validate_face(filepath)
        if not is_valid:
            if os.path.exists(filepath):
                os.remove(filepath)
            flash(f"AI Verification Failed: {msg}", 'error')
            return redirect(url_for('register'))

        # Save User Record to Database
        db = get_db()
        try:
            hashed_pw = generate_password_hash(password)
            db.execute(
                "INSERT INTO users (username, email, password_hash, face_encoding_path, is_verified) VALUES (?, ?, ?, ?, ?)",
                (username, email, hashed_pw, filepath, 1)
            )
            db.commit()
            flash('Registration & AI facial verification successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            if os.path.exists(filepath):
                os.remove(filepath)
            flash('Username or Email already exists.', 'error')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            flash(f"Welcome back, {user['username']}!", 'success')
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('vote'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')

@app.route('/vote', methods=['GET', 'POST'])
@login_required
def vote():
    db = get_db()
    user_id = session['user_id']

    # Fetch active election
    election = db.execute("SELECT * FROM elections WHERE status = 'active' ORDER BY id DESC LIMIT 1").fetchone()
    if not election:
        return render_template('wait.html', message="No active election currently in progress.")

    # Check if user already voted in this election
    existing_vote = db.execute(
        "SELECT * FROM votes WHERE user_id = ? AND election_id = ?", 
        (user_id, election['id'])
    ).fetchone()

    if existing_vote:
        flash('You have already cast your vote in this election.', 'info')
        return redirect(url_for('result', election_id=election['id']))

    if request.method == 'POST':
        candidate_id = request.form.get('candidate_id')
        if not candidate_id:
            flash('Please select a candidate.', 'error')
            return redirect(url_for('vote'))

        try:
            db.execute(
                "INSERT INTO votes (user_id, election_id, candidate_id) VALUES (?, ?, ?)",
                (user_id, election['id'], candidate_id)
            )
            db.commit()
            flash('Your vote has been securely recorded!', 'success')
            return redirect(url_for('result', election_id=election['id']))
        except sqlite3.IntegrityError:
            flash('Duplicate vote attempt detected.', 'error')
            return redirect(url_for('vote'))

    candidates = db.execute(
        "SELECT * FROM candidates WHERE election_id = ?", (election['id'],)
    ).fetchall()

    return render_template('vote.html', election=election, candidates=candidates)

@app.route('/result/<int:election_id>')
def result(election_id):
    db = get_db()
    election = db.execute("SELECT * FROM elections WHERE id = ?", (election_id,)).fetchone()
    
    if not election:
        flash('Election not found.', 'error')
        return redirect(url_for('index'))

    results = db.execute("""
        SELECT c.id, c.name, c.party, COUNT(v.id) AS vote_count
        FROM candidates c
        LEFT JOIN votes v ON c.id = v.candidate_id
        WHERE c.election_id = ?
        GROUP BY c.id
        ORDER BY vote_count DESC
    """, (election_id,)).fetchall()

    total_votes = sum(row['vote_count'] for row in results)

    return render_template('result.html', election=election, results=results, total_votes=total_votes)

@app.route('/admin/dashboard', methods=['GET', 'POST'])
@admin_required
def admin_dashboard():
    db = get_db()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create_election':
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            if title:
                db.execute("INSERT INTO elections (title, description) VALUES (?, ?)", (title, description))
                db.commit()
                flash('New election created successfully.', 'success')
            else:
                flash('Election title is required.', 'error')

        elif action == 'add_candidate':
            election_id = request.form.get('election_id')
            name = request.form.get('name', '').strip()
            party = request.form.get('party', '').strip()
            if election_id and name and party:
                db.execute("INSERT INTO candidates (election_id, name, party) VALUES (?, ?, ?)", (election_id, name, party))
                db.commit()
                flash('Candidate added successfully.', 'success')
            else:
                flash('All candidate details are required.', 'error')

        elif action == 'toggle_status':
            election_id = request.form.get('election_id')
            status = request.form.get('status')
            if election_id and status in ['active', 'closed']:
                db.execute("UPDATE elections SET status = ? WHERE id = ?", (status, election_id))
                db.commit()
                flash(f"Election status updated to '{status}'.", 'success')

        return redirect(url_for('admin_dashboard'))

    elections = db.execute("SELECT * FROM elections ORDER BY created_at DESC").fetchall()
    users = db.execute("SELECT id, username, email, is_verified, role FROM users ORDER BY created_at DESC").fetchall()

    return render_template('admin_dashboard.html', elections=elections, users=users)

@app.route('/logout')
def logout():
    session.clear()
    flash('Successfully logged out.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)