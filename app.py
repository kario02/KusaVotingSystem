from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_bcrypt import Bcrypt
import os
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
import mysql.connector
from datetime import datetime
from flask_mysqldb import MySQL
from flask_cors import CORS


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:brayookk7@localhost/kusa'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'brayookk7'
app.config['MYSQL_DB'] = 'kusa'
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
        {"id": c.id, "name": c.name, "position": c.position, "manifesto": c.manifesto, "image": c.image}
        for c in candidates
    ])

@app.route('/api/add_candidate', methods=['POST'])
def add_candidate():
    try:
        print("Raw Request Data:", request.form)

        name = request.form['name']
        position = request.form['position']
        manifesto = request.form['manifesto']
        image = request.files.get("image")

        if not name or not position or not manifesto:
            return jsonify({"error": "Missing required fields!"}), 400


        image_filename = "default.jpg"
        if image:
            image_filename = image.filename.replace(" ", "_")
            image_path = os.path.join(UPLOAD_FOLDER, image_filename)
            image.save(image_path)

        print(f"Received Data -> Name: {name}, Position: {position}, Manifesto: {manifesto}, Image:{image}")

        try:
            # Insert Data into MySQL
            cursor = mysql.connection.cursor()
            query = "INSERT INTO candidate (name, position, manifesto, image) VALUES (%s, %s, %s, %s)"
            values = (name, position, manifesto, image_filename)
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

    if not position:
        return jsonify({"error": "Position is required"}), 400

    candidates = Candidate.query.filter_by(position=position).all()
    candidates_data = [{"id": c.id, "name": c.name, "image": url_for('static', filename=f'uploads/{c.image}') if c.image else url_for('static', filename='default.png') } for c in candidates]

    return jsonify({"candidates": candidates_data})


@app.route('/vote_now', methods=['GET', 'POST'])
@login_required
def vote_now():
    query = text("SELECT DISTINCT position FROM candidate")
    positions = [row[0] for row in db.session.execute(query).fetchall()]  # Define positions
    session.setdefault('votes', {})  # Store selected votes in session

    if request.method == 'POST':
        position = request.form.get('position')
        candidate_id = request.form.get('candidate')
        session['votes'][position] = candidate_id  # Store vote in session

        # Move to next position
        next_index = positions.index(position) + 1
        if next_index < len(positions):
            return redirect(url_for('vote_now', position=positions[next_index]))
        else:
            return redirect(url_for('confirm_vote'))

    # Get current position
    position = request.args.get('position', positions[0]) if positions else None
    candidates = Candidate.query.filter_by(position=position).all() if position else []

    return render_template('vote_now.html', position=position, candidates=candidates, positions=positions)


@app.route('/confirm_vote', methods=['GET', 'POST'])
@login_required
def confirm_vote():
    votes = session.get('votes', {})

    if request.method == 'POST':
        voter_id = current_user.id
        for position, candidate_id in votes.items():
            new_vote = Vote(voter_id=voter_id, candidate_id=int(candidate_id), position=position,
                            timestamp=datetime.now())
            db.session.add(new_vote)

        db.session.commit()
        session.pop('votes', None)  # Clear session votes after submitting
        flash("Your vote has been submitted successfully!", "success")
        return redirect(url_for('dashboard'))

    return render_template('confirm_vote.html', votes=votes)


@app.route('/api/vote', methods=['POST'])
@login_required
def api_vote():
    data = request.get_json()
    position = data.get('position')
    candidate_id = data.get('candidate_id')
    session.setdefault('votes', {})
    session['votes'][position] = candidate_id
    return jsonify({"message": "Vote stored temporarily"}), 200


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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Ensure tables exist before running the app
    app.run(debug=True)
