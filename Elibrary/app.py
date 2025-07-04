from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import datetime
import re

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

def log_to_file(user, action, details):
    with open("actions.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now()} | {user} | {action} | {details}\n")

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
    employee_id = request.args.get('employee_id')
    department_id = request.args.get('department_id')
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
            award_applied_date = request.form.get(f'award_applied_date_{author_id}') or None
            cur.execute("""
                UPDATE elibrary.authors
                SET contribution = %s, applied_for_award = %s, award_applied_date = %s
                WHERE id = %s
            """, (contribution, applied_for_award, award_applied_date, author_id))
            log_to_file(session.get('login'), "update_author", f"author_id={author_id}, fields: contribution={contribution}, applied_for_award={applied_for_award}, award_applied_date={award_applied_date}")
        conn.commit()
    cur.execute('SELECT id, title, year_pub, in_rinc FROM elibrary.articles WHERE id = %s', (article_id,))
    article = cur.fetchone()
    cur.execute('SELECT id, author_name, contribution, applied_for_award, award_applied_date FROM elibrary.authors WHERE article_id = %s', (article_id,))
    authors = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('article.html', article=article, authors=authors, employee_id=employee_id, department_id=department_id)
    
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

@app.route('/add_department', methods=['GET', 'POST'])
def add_department():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name'].strip()
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO elibrary.departments (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (name,))
            conn.commit()
        finally:
            cur.close()
            conn.close()
        return redirect(url_for('add_department'))
    return render_template('add_department.html')

@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM elibrary.departments ORDER BY name")
    departments = cur.fetchall()
    if request.method == 'POST':
        fio = request.form['fio'].strip()
        dep_ids = request.form.getlist('departments')
        cur.execute("INSERT INTO elibrary.employees (FIO) VALUES (%s) RETURNING id", (fio,))
        emp_id = cur.fetchone()[0]
        for dep_id in dep_ids:
            cur.execute("""
                INSERT INTO elibrary.employee_departments (employee_id, department_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
            """, (emp_id, dep_id))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('add_employee'))
    cur.close()
    conn.close()
    return render_template('add_employee.html', departments=departments)

@app.route('/link_articles/<int:employee_id>', methods=['GET', 'POST'])
def link_articles(employee_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT FIO FROM elibrary.employees WHERE id = %s", (employee_id,))
    fio = cur.fetchone()[0]

    # Получаем все связанные статьи
    cur.execute("""
        SELECT a.id, a.title
        FROM elibrary.articles a
        JOIN elibrary.employee_articles ea ON a.id = ea.article_id
        WHERE ea.employee_id = %s
    """, (employee_id,))
    linked_articles = cur.fetchall()
    linked_ids = set(id for id, _ in linked_articles)

    # Получаем подходящие по автору, но не связанные
    fio_parts = fio.split()
    if len(fio_parts) >= 2:
        surname = fio_parts[0]
        first_initial = fio_parts[1][0]
        fio_pattern = f"{surname} {first_initial}.%"
    else:
        fio_pattern = fio + '%'
    cur.execute("""
        SELECT DISTINCT a.id, a.title
        FROM elibrary.articles a
        JOIN elibrary.authors au ON a.id = au.article_id
        WHERE au.author_name ILIKE %s
          AND a.id NOT IN (
              SELECT article_id FROM elibrary.employee_articles WHERE employee_id = %s
          )
    """, (fio_pattern, employee_id))
    candidate_articles = cur.fetchall()

    if request.method == 'POST':
        selected = set(map(int, request.form.getlist('articles')))
        # Удаляем все старые связи
        cur.execute("DELETE FROM elibrary.employee_articles WHERE employee_id = %s", (employee_id,))
        # Добавляем новые связи
        for article_id in selected:
            cur.execute("""
                INSERT INTO elibrary.employee_articles (employee_id, article_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
            """, (employee_id, article_id))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('link_articles', employee_id=employee_id))
    cur.close()
    conn.close()
    return render_template(
        'link_articles.html',
        fio=fio,
        linked_articles=linked_articles,
        candidate_articles=candidate_articles,
        employee_id=employee_id
    )

@app.route('/department_employees/<int:department_id>')
def department_employees(department_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM elibrary.departments WHERE id = %s", (department_id,))
    dep_name = cur.fetchone()[0]
    cur.execute("""
        SELECT e.id, e.FIO
        FROM elibrary.employees e
        JOIN elibrary.employee_departments ed ON e.id = ed.employee_id
        WHERE ed.department_id = %s
    """, (department_id,))
    employees = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('department_employees.html', dep_name=dep_name, employees=employees, department_id=department_id)

@app.route('/employee_articles/<int:employee_id>')
def employee_articles(employee_id):
    department_id = request.args.get('department_id')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT FIO FROM elibrary.employees WHERE id = %s", (employee_id,))
    fio = cur.fetchone()[0]
    # Получаем все статьи, связанные с сотрудником
    cur.execute("""
        SELECT a.id, a.title, 
               COALESCE(au.applied_for_award, FALSE), 
               a.year_pub
        FROM elibrary.articles a
        JOIN elibrary.employee_articles ea ON a.id = ea.article_id
        LEFT JOIN elibrary.authors au ON a.id = au.article_id AND au.author_name LIKE %s
        WHERE ea.employee_id = %s
    """, (fio + '%', employee_id))
    articles = cur.fetchall()
    cur.close()
    conn.close()
    # Сортировка: сначала не подано (False), потом подано (True), внутри — по году убыванию
    articles.sort(key=lambda x: (x[2], -x[3]))
    return render_template('employee_articles.html', fio=fio, articles=articles, employee_id=employee_id, department_id=department_id)

@app.route('/manual_link/<int:employee_id>', methods=['POST'])
def manual_link(employee_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    article_id = request.form.get('manual_article_id')
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO elibrary.employee_articles (employee_id, article_id)
            VALUES (%s, %s) ON CONFLICT DO NOTHING
        """, (employee_id, article_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('link_articles', employee_id=employee_id))

@app.route('/add_article', methods=['GET', 'POST'])
def add_article():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        article_id = request.form.get('article_id')
        title = request.form.get('title')
        year_pub = request.form.get('year_pub')
        in_rinc = request.form.get('in_rinc') == 'on'
        authors_str = request.form.get('authors')
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO elibrary.articles (id, title, year_pub, in_rinc)
                VALUES (%s, %s, %s, %s)
            """, (article_id, title, year_pub, in_rinc))
            # Добавляем авторов
            authors = [a.strip() for a in authors_str.split(',') if a.strip()]
            for author in authors:
                cur.execute("""
                    INSERT INTO elibrary.authors (article_id, author_name, contribution, applied_for_award)
                    VALUES (%s, %s, %s, %s)
                """, (article_id, author, 0, False))
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for('article_detail', article_id=article_id))
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            return f"Ошибка при добавлении статьи: {e}"
    return render_template('add_article.html')

@app.route('/departments_list')
def departments_list():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM elibrary.departments ORDER BY name")
    departments = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('departments_list.html', departments=departments)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)