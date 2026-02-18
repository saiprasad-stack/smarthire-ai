from flask import Flask, render_template, request, redirect, session
from config import *
import psycopg2
import os
from resume_analyzer import extract_text_from_pdf, calculate_similarity

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")


# PostgreSQL Connection Function
def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")

    conn = psycopg2.connect(database_url)
    return conn



# Home Page
@app.route('/')
def index():
    return render_template('index.html')


# Register
@app.route('/register', methods=['POST'])
def register():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    role = request.form['role']

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
        (name, email, password, role)
    )
    conn.commit()
    cur.close()
    conn.close()

    return redirect('/')


# Login
@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM users WHERE email=%s AND password=%s",
        (email, password)
    )
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        session['user_id'] = user[0]
        session['role'] = user[4]
        return redirect('/dashboard')

    return "Invalid Credentials"


# Dashboard
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs")
    jobs = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('dashboard.html', role=session['role'], jobs=jobs)


# Post Job (HR only)
@app.route('/post_job', methods=['POST'])
def post_job():
    if session.get('role') != 'hr':
        return "Unauthorized"

    title = request.form['title']
    description = request.form['description']

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO jobs (title, description, posted_by) VALUES (%s, %s, %s)",
        (title, description, session['user_id'])
    )
    conn.commit()
    cur.close()
    conn.close()

    return redirect('/dashboard')


# Apply for Job (Candidate only)
@app.route('/apply/<int:job_id>', methods=['POST'])
def apply(job_id):
    if session.get('role') != 'candidate':
        return "Unauthorized"

    file = request.files['resume']
    filepath = os.path.join('uploads', file.filename)
    file.save(filepath)

    resume_text = extract_text_from_pdf(filepath)

    conn = get_db_connection()
    cur = conn.cursor()

    # Get Job Description
    cur.execute("SELECT description FROM jobs WHERE id=%s", (job_id,))
    job = cur.fetchone()
    job_description = job[0]

    # Calculate Score
    score = calculate_similarity(resume_text, job_description)

    # Store Application
    cur.execute(
        "INSERT INTO applications (user_id, job_id, resume_path, score) VALUES (%s, %s, %s, %s)",
        (session['user_id'], job_id, filepath, score)
    )

    conn.commit()
    cur.close()
    conn.close()

    return f"Application submitted! Match Score: {score}%"


# View Applications (HR only)
@app.route('/view_applications/<int:job_id>')
def view_applications(job_id):
    if session.get('role') != 'hr':
        return "Unauthorized"

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT users.name, applications.resume_path, applications.score
        FROM applications
        JOIN users ON applications.user_id = users.id
        WHERE applications.job_id = %s
        ORDER BY applications.score DESC
    """, (job_id,))

    applications = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('applications.html', applications=applications)


# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


if __name__ == "__main__":
    app.run()
