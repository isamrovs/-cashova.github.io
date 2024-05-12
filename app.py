from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
from datetime import datetime, date, timedelta
import random
from flask_login import UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Задайте ваш ключ для сессий
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parskats.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login_register'


# Модель пользователя
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(100), nullable=False)

    @property
    def password(self):
        raise AttributeError('Password is not readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Модель для финансовых записей
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_type = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Добавляем связь с пользователем
    user = db.relationship('User', backref=db.backref('items', lazy=True))


@app.route('/login_register', methods=['GET', 'POST'])
def login_register():
    if request.method == 'POST':
        form_type = request.form['form_type']  # Определение типа формы (регистрация или авторизация)
        
        if form_type == 'register':  # Регистрация нового пользователя
            username = request.form['username']
            password = request.form['password']
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('Lietotāja vārds jau ir aizņemts!', 'error')
            else:
                new_user = User(username=username, password=password)
                db.session.add(new_user)
                db.session.commit()
                flash('Jūs veisksmīgi reģistrējušies!', 'success')
                return redirect(url_for('login_register'))
        
        elif form_type == 'login':  # Авторизация пользователя
            username = request.form['username']
            password = request.form['password']
            user = User.query.filter_by(username=username).first()
            if user and user.verify_password(password):
                login_user(user)
                flash('Jūs veiksmīgi iejejāt sistēmā!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Nepareizs lietotāja vārds vai parole', 'error')

    return render_template('login_register.html')


# Страница выхода из учетной записи
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login_register'))


# Главная страница
@app.route('/')
def index():
    return render_template('index.html')


# Страница финансового отчета
@app.route('/parskats')
@login_required
def parskats():
    return render_template('parskats.html')


# Страница добавления записи о финансах
@app.route('/pievienosana', methods=['GET', 'POST'])
@login_required
def pievienosana():
    if request.method == 'POST':
        item_type = request.form['item_type']
        category = request.form['category']
        name = request.form['name']
        amount = request.form['amount']
        date_str = request.form['date']
        date = datetime.strptime(date_str, '%Y-%m-%d').date()

        new_item = Item(item_type=item_type, category=category, name=name, amount=amount, date=date, user_id=current_user.id)
        db.session.add(new_item)
        db.session.commit()

        flash('Darījums veiskmīgi pievienots!', 'success')
        return redirect(url_for('pievienosana'))
    else:
        return render_template('pievienosana.html')


# Получение финансовых данных
@app.route('/get_financial_data', methods=['GET', 'POST'])
@login_required
def get_financial_data():
    # Получаем текущего пользователя
    user_id = current_user.id

    # Получаем текущую дату
    current_date = date.today()
    # Получаем первый день текущего месяца
    first_day_of_month = current_date.replace(day=1)
    # Получаем последний день текущего месяца
    last_day_of_month = current_date.replace(day=current_date.day)

    # Вычисляем общие расходы и доходы за все время
    total_expenses_all_time = db.session.query(db.func.sum(Item.amount)).filter(
        Item.user_id == user_id, Item.item_type == 'expense').scalar() or 0
    total_income_all_time = db.session.query(db.func.sum(Item.amount)).filter(
        Item.user_id == user_id, Item.item_type == 'income').scalar() or 0
    total_balance_all_time = total_income_all_time - total_expenses_all_time

    # Вычисляем общие расходы и доходы за текущий месяц
    total_expenses_month = db.session.query(db.func.sum(Item.amount)).filter(
        Item.user_id == user_id, Item.item_type == 'expense',
        Item.date.between(first_day_of_month, last_day_of_month)).scalar() or 0
    total_income_month = db.session.query(db.func.sum(Item.amount)).filter(
        Item.user_id == user_id, Item.item_type == 'income',
        Item.date.between(first_day_of_month, last_day_of_month)).scalar() or 0
    total_balance_month = total_income_month - total_expenses_month

    # Проверяем, переданы ли параметры для выбранного периода
    if request.method == 'POST':
        start_date_str = request.json.get('start_date', None)
        end_date_str = request.json.get('end_date', None)

        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

            # Вычисляем расходы и доходы за выбранный период
            total_expenses_period = db.session.query(db.func.sum(Item.amount)).filter(
                Item.user_id == user_id, Item.item_type == 'expense',
                Item.date.between(start_date, end_date)).scalar() or 0
            total_income_period = db.session.query(db.func.sum(Item.amount)).filter(
                Item.user_id == user_id, Item.item_type == 'income',
                Item.date.between(start_date, end_date)).scalar() or 0
            total_balance_period = total_income_period - total_expenses_period

            selected_period_available = True
        else:
            total_expenses_period = 0
            total_income_period = 0
            total_balance_period = 0
            selected_period_available = False
    else:
        total_expenses_period = 0
        total_income_period = 0
        total_balance_period = 0
        selected_period_available = False

    # Строим категориальное распределение для расходов и доходов за текущий месяц
    expenses_data_month = db.session.query(Item.category, db.func.sum(Item.amount)).filter(
        Item.user_id == user_id, Item.item_type == 'expense',
        Item.date.between(first_day_of_month, last_day_of_month)).group_by(
        Item.category).all()
    income_data_month = db.session.query(Item.category, db.func.sum(Item.amount)).filter(
        Item.user_id == user_id, Item.item_type == 'income',
        Item.date.between(first_day_of_month, last_day_of_month)).group_by(
        Item.category).all()

    # Формируем данные для текущего месяца
    expenses_categories_month = [data[0] for data in expenses_data_month]
    expenses_amounts_month = [data[1] for data in expenses_data_month]
    income_categories_month = [data[0] for data in income_data_month]
    income_amounts_month = [data[1] for data in income_data_month]

    expenses_colors_month = ['#' + ("%06x" % random.randint(0, 0xFFFFFF)) for _ in range(len(expenses_categories_month))]
    income_colors_month = ['#' + ("%06x" % random.randint(0, 0xFFFFFF)) for _ in range(len(income_categories_month))]

    # Проверяем, переданы ли параметры для выбранного периода
    if selected_period_available:
        # Строим категориальное распределение для расходов и доходов за выбранный период
        expenses_data_period = db.session.query(Item.category, db.func.sum(Item.amount)).filter(
            Item.user_id == user_id, Item.item_type == 'expense',
            Item.date.between(start_date, end_date)).group_by(
            Item.category).all()
        income_data_period = db.session.query(Item.category, db.func.sum(Item.amount)).filter(
            Item.user_id == user_id, Item.item_type == 'income',
            Item.date.between(start_date, end_date)).group_by(
            Item.category).all()

        # Формируем данные для выбранного периода
        expenses_categories_period = [data[0] for data in expenses_data_period]
        expenses_amounts_period = [data[1] for data in expenses_data_period]
        income_categories_period = [data[0] for data in income_data_period]
        income_amounts_period = [data[1] for data in income_data_period]

        expenses_colors_period = ['#' + ("%06x" % random.randint(0, 0xFFFFFF)) for _ in range(len(expenses_categories_period))]
        income_colors_period = ['#' + ("%06x" % random.randint(0, 0xFFFFFF)) for _ in range(len(income_categories_period))]

    else:
        expenses_categories_period = []
        expenses_amounts_period = []
        income_categories_period = []
        income_amounts_period = []
        expenses_colors_period = []
        income_colors_period = []

    # Формируем данные для возврата на клиент
    data = {
        "total_balance_all_time": total_balance_all_time,
        "total_income_all_time": total_income_all_time,
        "total_expenses_all_time": total_expenses_all_time,
        "total_expenses_month": total_expenses_month,
        "total_income_month": total_income_month,
        "total_balance_month": total_balance_month,
        "total_expenses_period": total_expenses_period,
        "total_income_period": total_income_period,
        "total_balance_period": total_balance_period,
        "selected_period_available": selected_period_available,
        "expenses_categories_month": expenses_categories_month,
        "expenses_amounts_month": expenses_amounts_month,
        "expenses_colors_month": expenses_colors_month,
        "income_categories_month": income_categories_month,
        "income_amounts_month": income_amounts_month,
        "income_colors_month": income_colors_month,
        "expenses_categories_period": expenses_categories_period,
        "expenses_amounts_period": expenses_amounts_period,
        "expenses_colors_period": expenses_colors_period,
        "income_categories_period": income_categories_period,
        "income_amounts_period": income_amounts_period,
        "income_colors_period": income_colors_period
    }

    # Отправляем данные на клиент в формате JSON
    return jsonify(data)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)