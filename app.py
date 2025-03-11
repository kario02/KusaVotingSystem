from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
from flask_mysqldb import MySQL
from flask_cors import CORS
from flask_session import Session
import os
import pymysql
import mysql.connector
import pandas as pd


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:brayookk7@localhost/kusa'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'brayookk7'
app.config['MYSQL_DB'] = 'kusa'
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True
Session(app)
CORS(app)

mysql=MySQL(app)
# db.init_app(app)
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.init_app(app)
login_manager.login_view = 'login'


UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

candidates = []

def get_db_connection():
    return pymysql.connect(host='localhost', user='root', password='brayookk7', database='kusa')

# Define models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="voter")  # Optional: Track user roles

    def set_password(self, password):
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)


class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    position = db.Column(db.String(255), nullable=False)
    manifesto = db.Column(db.Text, nullable=False)
    school = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    voter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Assuming you have a User model
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate.id'), nullable=False)
    position = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship (optional)
    voter = db.relationship('User', backref=db.backref('votes', lazy=True))
    candidate = db.relationship('Candidate', backref=db.backref('votes', lazy=True))

    def __repr__(self):
        return f'<Vote {self.voter_id} -> {self.candidate_id}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('kusa.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))


        flash('Invalid credentials, please try again.', 'danger')

    return render_template('login.html')

@app.route('/sign_up', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('sign_up.html')

@app.route('/dashboard')
@login_required
def dashboard():
    cursor = mysql.connection.cursor()

    cursor.execute("SELECT id, name, position, manifesto, image FROM candidate")
    candidates = cursor.fetchall()


    # Convert candidates to a list of dictionaries
    candidates_list = [
        {"id": c[0], "name": c[1], "position": c[2], "manifesto": c[3], "image": c[4]}
        for c in candidates
    ]
    # Fetch voting progress (Modify this based on your DB structure)
    cursor.execute("""
           SELECT TIME(timestamp) AS vote_time, COUNT(*) AS vote_count
           FROM vote
           GROUP BY vote_time
           ORDER BY vote_time
       """)
    vote_data = cursor.fetchall()
    cursor.close()


    # Convert vote data into format suitable for Chart.js
    voting_progress = {
        "labels": [str(row[0]) for row in vote_data],  # Time of votes
        "data": [row[1] for row in vote_data]  # Number of votes
    }
    return render_template('dashboard.html', candidates=candidates_list, voting_progress=voting_progress, user=current_user)

@app.route('/candidates', methods=['GET'])
def gets_candidates():
    return render_template('candidates.html')

@app.route('/api/candidates', methods=['GET'])
def get_candidates():
    candidates = Candidate.query.all()
    return jsonify([
        {"id": c.id, "name": c.name, "position": c.position, "manifesto": c.manifesto, "school": c.school, "image": c.image}
        for c in candidates
    ])

@app.route('/api/add_candidate', methods=['POST'])
def add_candidate():
    try:
        print("Raw Request Data:", request.form)

        name = request.form['name']
        position = request.form['position']
        manifesto = request.form['manifesto']
        school = request.form['school']
        image = request.files.get("image")

        if not name or not position or not manifesto or not school:
            return jsonify({"error": "Missing required fields!"}), 400


        image_filename = "default.jpg"
        if image:
            image_filename = image.filename.replace(" ", "_")
            image_path = os.path.join(UPLOAD_FOLDER, image_filename)
            image.save(image_path)

        print(f"Received Data -> Name: {name}, Position: {position}, Manifesto: {manifesto}, school: {school}, Image:{image}")

        try:
            # Insert Data into MySQL
            cursor = mysql.connection.cursor()
            query = "INSERT INTO candidate (name, position, manifesto, school, image) VALUES (%s, %s, %s, %s, %s)"
            values = (name, position, manifesto, school, image_filename)
            cursor.execute(query, values)
            mysql.connection.commit()
            cursor.close()
        except Exception as db_error:
            return jsonify({"error": f"Database Error: {str(db_error)}"}), 500


        return jsonify({"message": "Candidate added successfully!"}), 201
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/get_candidates', methods=['GET'])
@login_required
def api_get_candidates():
    position = request.args.get('position')
    school = request.args.get('school')

    if not position or not school:
        return jsonify({"error": "Missing Position or School"}), 400

    candidates = Candidate.query.filter_by(position=position, school=school).all()
    candidates_data = [{"id": c.id, "name": c.name, "image": url_for('static', filename=f'uploads/{c.image}') if c.image else url_for('static', filename='default.png') } for c in candidates]

    return jsonify({"candidates": candidates_data})


@app.route('/vote_now', methods=['GET', 'POST'])
@login_required
def vote_now():
    school = request.args.get('school')  # Get selected school from query parameters
    if not school:
        return redirect(url_for('choose_school'))  # Redirect if no school is selected

    query = text("SELECT DISTINCT position FROM candidate WHERE school = :school")
    positions = [row[0] for row in db.session.execute(query, {"school": school}).fetchall()]
    session['votes'] = {}  # Store selected votes in session

    if request.method == 'POST':
        position = request.form.get('position')
        candidate_id = request.form.get('candidate')
        session['votes'][position] = candidate_id

        # Move to next position
        next_index = positions.index(position) + 1
        if next_index < len(positions):
            return redirect(url_for('vote_now', school=school, position=positions[next_index]))
        else:
            return redirect(url_for('confirm_vote'))

    # Get current position
    position = request.args.get('position', positions[0]) if positions else None
    candidates = Candidate.query.filter_by(position=position, school=school).all() if position else []

    return render_template('vote_now.html', position=position, candidates=candidates, positions=positions,
                           school=school)


@app.route('/confirm_vote', methods=['GET', 'POST'])
@login_required
def confirm_vote():
    print("🔵 confirm_vote() route accessed!")

    # Fetch votes from session
    votes = session.get('votes', {})
    print("Votes stored in session before submission:", votes)  # Debugging

    if not votes:  # Handle case where no votes exist
        print("❌ ERROR: No votes found in session!")
        flash("No votes found. Please vote before confirming.", "danger")
        return redirect(url_for('vote_now'))

    if request.method == 'POST':
        voter_id = current_user.id
        print("Voter ID:", voter_id)  # Debugging step

        for position, candidate_id in votes.items():
            print(f"Saving Vote: {position} -> {candidate_id}")  # Debugging step
            new_vote = Vote(
                voter_id=voter_id,
                candidate_id=int(candidate_id),
                position=position,
                timestamp=datetime.now()
            )
            db.session.add(new_vote)

        try:
            db.session.commit()
            print("✅ Vote successfully saved to the database.")
            session.pop('votes', None)  # Clear session votes after submitting
            flash("Your vote has been submitted successfully!", "success")
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error saving votes:", e)
            flash("An error occurred while saving your vote. Please try again.", "danger")

    return render_template('confirm_vote.html', votes=votes)


@app.route('/api/vote', methods=['POST'])
@login_required
def api_vote():
    data = request.get_json()
    position = data.get('position')
    candidate_id = data.get('candidate_id')

    session.setdefault('votes', {})
    session['votes'][position] = candidate_id
    session.modified = True

    print("Votes stored in session:", session.get('votes'))

    return jsonify({"message": "Vote stored temporarily"}), 200

@app.route('/api/store_votes', methods=['POST'])
@login_required
def store_votes():
    data = request.json  # Get votes from frontend
    if not data:
        return jsonify({"error": "No votes received"}), 400  # Handle empty votes

    session['votes'] = data  # Store votes in session
    session.modified = True  # Ensure session updates correctly

    print("✅ Votes stored in session:", session['votes'])  # Debugging
    return jsonify({"message": "Votes stored successfully", "votes": session['votes']})


@app.route('/analytics')
def analytics():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM vote")
    total_votes = cursor.fetchone()[0]

    cursor.execute("SELECT position, COUNT(*) FROM vote GROUP BY position")
    votes_per_position = cursor.fetchall()

    cursor.execute("SELECT DISTINCT position FROM candidate")
    positions = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT school FROM user")
    schools = [row[0] for row in cursor.fetchall()]

    conn.close()
    return render_template('analytics.html',
                           total_votes=total_votes,
                           votes_per_position=votes_per_position,
                           positions=positions,
                           schools=schools)


@app.route('/api/analytics_data')
def analytics_data():
    conn = get_db_connection()
    cursor = conn.cursor()

    position = request.args.get("position")
    school = request.args.get("school")
    date = request.args.get("date")

    filters = []
    params = []

    if position and position.lower() != "all":
        filters.append("candidates.position = %s")
        params.append(position)

    if school and school.lower() != "all":
        filters.append("user.school = %s")
        params.append(school)

    if date:
        filters.append("DATE(votes.timestamp) = %s")
        params.append(date)

    filter_query = " AND ".join(filters)
    query = f"""
        SELECT candidate.name, COUNT(vote.candidate_id) AS vote_count
        FROM candidate 
        LEFT JOIN vote ON candidate.id = vote.candidate_id 
        LEFT JOIN user ON vote.voter_id = user.id
        {('WHERE ' + filter_query) if filters else ''}
        GROUP BY candidate.id
    """
    cursor.execute(query, tuple(params))
    candidate_data = [{"name": row[0], "votes": row[1]} for row in cursor.fetchall()]

    cursor.execute("SELECT COUNT(*) FROM vote")
    total_votes = cursor.fetchone()[0]

    cursor.execute("SELECT position, COUNT(*) FROM vote GROUP BY position")
    position_data = [{"position": row[0], "votes": row[1]} for row in cursor.fetchall()]

    conn.close()
    return jsonify({"total_votes": total_votes, "candidates": candidate_data, "positions": position_data})


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('kusa'))
@app.route('/kusa')
def kusa():
    return render_template('kusa.html')

@app.route('/voting_overview')
def voting_overview():
    return render_template('voting_overview.html')


@app.route('/view_results')
@login_required
def view_results():
    candidates = Candidate.query.all()

    # Count votes per candidate
    results = {}
    total_votes = Vote.query.count()  # Get total votes cast

    for candidate in candidates:
        vote_count = Vote.query.filter_by(candidate_id=candidate.id).count()
        percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0

        results[candidate.id] = {
            "name": candidate.name,
            "position": candidate.position,
            "votes": vote_count,
            "percentage": round(percentage, 2),
        }

    return render_template('view_results.html', results=results)

@app.route('/get_votes')
def get_votes():
    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT c.name, c.position, COUNT(v.id) AS votes
        FROM candidate c
        LEFT JOIN vote v ON c.id = v.id
        GROUP BY c.id, c.name, c.position
    """)
    results = cursor.fetchall()
    cursor.close()

    # Convert results to HTML
    vote_html = "".join([f"<p><strong>{r[0]}</strong> ({r[1]}) - {r[2]} votes</p>" for r in results])

    return jsonify({"html": vote_html})

@app.route('/choose_school', methods=['GET'])
@login_required
def choose_school():
    schools = [
        "School of Agricultural and Environmental Sciences",
        "School of Business, Economics and Tourism",
        "School of Education",
        "School of Engineering and Architecture",
        "School of Health Sciences",
        "School of Law, Arts and Social Sciences",
        "School of Pure And Applied Sciences"
    ]
    return render_template('choose_school.html', schools=schools)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Ensure tables exist before running the app
    app.run(debug=True)
