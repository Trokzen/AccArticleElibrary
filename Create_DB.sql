-- Создание схемы "elibrary"
CREATE SCHEMA IF NOT EXISTS elibrary;

-- Переключение на схему "elibrary"
SET search_path TO elibrary;

-- Создание таблицы "Articles" (Статьи)
CREATE TABLE IF NOT EXISTS elibrary.articles (
    id INTEGER PRIMARY KEY,          -- Уникальный идентификатор статьи
    title TEXT NOT NULL,             -- Название статьи
    in_rinc BOOLEAN NOT NULL         -- Включена ли статья в РИНЦ ("Да"/"Нет")
);

-- Создание таблицы "Authors" (Авторы)
CREATE TABLE IF NOT EXISTS elibrary.authors (
    id SERIAL PRIMARY KEY,           -- Уникальный идентификатор записи
    article_id INTEGER NOT NULL,     -- ID статьи (внешний ключ)
    author_name TEXT NOT NULL,       -- Фамилия и инициалы автора
    contribution REAL CHECK(contribution BETWEEN 0 AND 100), -- Вклад автора в статью (от 0 до 100%)
    applied_for_award BOOLEAN NOT NULL, -- Подал ли автор статью на премию
    award_applied_date DATE,         -- Дата подачи на премию
    FOREIGN KEY (article_id) REFERENCES elibrary.articles(id) ON DELETE CASCADE
);

-- Создание таблицы "Users" (Пользователи)
CREATE TABLE IF NOT EXISTS elibrary.users (
    id SERIAL PRIMARY KEY,           -- Уникальный идентификатор пользователя
    login TEXT NOT NULL UNIQUE,      -- Логин пользователя (уникальный)
    password_hash TEXT NOT NULL,     -- Хэш пароля
    email TEXT UNIQUE,               -- Email пользователя (опционально, уникален)
    role TEXT DEFAULT 'user'         -- Роль пользователя (например, 'admin', 'user')
);

-- Таблица подразделений
CREATE TABLE IF NOT EXISTS elibrary.departments (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- Таблица сотрудников
CREATE TABLE IF NOT EXISTS elibrary.employees (
    id SERIAL PRIMARY KEY,
    FIO TEXT NOT NULL
);

-- Связующая таблица "сотрудник-подразделение" (многие ко многим)
CREATE TABLE IF NOT EXISTS elibrary.employee_departments (
    employee_id INTEGER NOT NULL,
    department_id INTEGER NOT NULL,
    PRIMARY KEY (employee_id, department_id),
    FOREIGN KEY (employee_id) REFERENCES elibrary.employees(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES elibrary.departments(id) ON DELETE CASCADE
);

-- Связующая таблица "сотрудник-статья" (многие ко многим)
CREATE TABLE IF NOT EXISTS elibrary.employee_articles (
    employee_id INTEGER NOT NULL,
    article_id INTEGER NOT NULL,
    PRIMARY KEY (employee_id, article_id),
    FOREIGN KEY (employee_id) REFERENCES elibrary.employees(id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES elibrary.articles(id) ON DELETE CASCADE
);

-- Индекс для ускорения поиска по логину
CREATE INDEX IF NOT EXISTS idx_users_login ON elibrary.users(login);
