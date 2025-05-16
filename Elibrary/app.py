from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Замените на свой секретный ключ

def get_db_connection():
    return psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password="1234",
        host="localhost",
        port="5432"
    )

@app.route('/')
def index():
    search_id = request.args.get('search_id', '').strip()
    search_title = request.args.get('search_title', '').strip()
    conn = get_db_connection()
    cur = conn.cursor()
    if search_id:
        cur.execute('SELECT id, title FROM elibrary.articles WHERE id = %s', (search_id,))
    elif search_title:
        cur.execute('SELECT id, title FROM elibrary.articles WHERE title ILIKE %s', (f'%{search_title}%',))
    else:
        cur.execute('SELECT id, title FROM elibrary.articles')
    articles = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', articles=articles)

@app.route('/article/<int:article_id>', methods=['GET', 'POST'])
def article_detail(article_id):
    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == 'POST':
        if 'user_id' not in session:
            cur.close()
            conn.close()
            return "Редактирование доступно только авторизованным пользователям!"
        # Получаем всех авторов этой статьи
        cur.execute('SELECT id FROM elibrary.authors WHERE article_id = %s', (article_id,))
        author_ids = [row[0] for row in cur.fetchall()]
        for author_id in author_ids:
            contribution = float(request.form.get(f'contribution_{author_id}', 0))
            applied_for_award = f'applied_for_award_{author_id}' in request.form
            cur.execute("""
                UPDATE elibrary.authors
                SET contribution = %s, applied_for_award = %s
                WHERE id = %s
            """, (contribution, applied_for_award, author_id))
        conn.commit()
    cur.execute('SELECT id, title, in_rinc FROM elibrary.articles WHERE id = %s', (article_id,))
    article = cur.fetchone()
    cur.execute('SELECT id, author_name, contribution, applied_for_award FROM elibrary.authors WHERE article_id = %s', (article_id,))
    authors = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('article.html', article=article, authors=authors)
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']
        password_hash = generate_password_hash(password)
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO elibrary.users (login, password_hash) VALUES (%s, %s)",
                (login, password_hash)
            )
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for('login'))
        except Exception as e:
            cur.close()
            conn.close()
            return f"Ошибка регистрации: {e}"
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash FROM elibrary.users WHERE login = %s", (login,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['login'] = login
            return redirect(url_for('index'))
        else:
            return "Неверный логин или пароль"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)