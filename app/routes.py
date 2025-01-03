from datetime import datetime, timedelta, time, date
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from .models import *
from . import db, csrf
from .utils import *
from .forms import SelectServicesForm, CarForm
from sqlalchemy import text
import os
import logging

logging.basicConfig(level=logging.DEBUG)

main = Blueprint('main', __name__)

def calculate_end_time(appointment_time, service_ids):
    """Рассчитывает время окончания заказа на основе выбранных услуг."""
    total_duration = sum(Service.query.get(service_id).duration for service_id in service_ids)
    return (datetime.strptime(appointment_time, '%H:%M') + timedelta(minutes=total_duration)).strftime('%H:%M')

def create_task_for_order(order_id, employee_id):
    """Создает задачу для заказа."""
    new_task = Task(
        employee_id=employee_id,
        order_id=order_id,
        status='pending'
    )
    db.session.add(new_task)
    db.session.commit()

def get_available_mechanic():
    """Возвращает доступного механика."""
    mechanic = Employee.query.filter_by(role='mechanic').first()
    if not mechanic:
        raise ValueError("Нет доступных механиков")
    return mechanic

def is_valid_appointment_date(date, appointment_time):
    """Проверяет валидность даты и времени записи."""
    current_time = datetime.now()
    opening_time = time(9, 0)
    closing_time = time(17, 0)

    if date < current_time.date():
        return False
    
    if date == current_time.date() and current_time.time() >= closing_time:
        return False

    if datetime.strptime(appointment_time, '%H:%M').time() < opening_time or datetime.strptime(appointment_time, '%H:%M').time() >= closing_time:
        return False
    
    return True

def get_available_slots_for_date(date_str, selected_service_ids):
    """Получает доступные слоты для даты."""
    if isinstance(date_str, date):
        date_obj = date_str
    else:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

    existing_orders = Order.query.filter_by(appointment_date=date_obj).all()

    total_duration = sum(Service.query.get(service_id).duration for service_id in selected_service_ids)

    work_start = time(9, 0)
    work_end = time(17, 0)
    slot_duration = timedelta(minutes=30)
    current_time = datetime.combine(date_obj, work_start)
    available_slots = []

    while current_time.time() < work_end:
        slot_start_str = current_time.strftime('%H:%M')
        slot_end_time = current_time + timedelta(minutes=total_duration)

        is_available = True
        for order in existing_orders:
            if order.end_time is None:
                continue

            order_start = datetime.combine(date_obj, order.appointment_time)
            order_end = datetime.combine(date_obj, order.end_time)

            if not (slot_end_time <= order_start or current_time >= order_end):
                is_available = False
                break

        available_slots.append((slot_start_str, is_available))
        current_time += slot_duration

    return available_slots

def is_slot_available(slot_start_time, service_duration, booked_slots):
    """Проверяет доступность слота."""
    slot_end_time = (datetime.combine(datetime.today(), slot_start_time) + timedelta(minutes=service_duration)).time()

    for booked_start, booked_end in booked_slots.values():
        if booked_start is None or booked_end is None:
            continue

        if slot_start_time < booked_end and slot_end_time > booked_start:
            return False

    return True

def get_mechanic_tasks(employee_id):
    """Получает задачи механика."""
    tasks = (
        Task.query
        .join(Order, Task.order_id == Order.id)
        .join(Car, Order.car_id == Car.id)
        .join(Client, Order.client_id == Client.id)
        .join(Service, Order.services)
        .filter(Task.employee_id == employee_id)
        .order_by(Order.appointment_date, Order.appointment_time)
        .all()
    )
    return tasks

@main.route('/')
def index():
    """Обрабатывает главную страницу."""
    if 'user_id' in session:
        role = session.get('role')
        if role == 'client':
            return redirect(url_for('main.client_dashboard'))
        elif role == 'mechanic':
            return redirect(url_for('main.mechanic_dashboard'))
        elif role == 'manager':
            return redirect(url_for('main.manager_dashboard'))
    return redirect(url_for('main.login'))

@main.route('/login', methods=['GET', 'POST'])
def login():
    """Обрабатывает вход пользователя."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = Employee.query.filter_by(email=email).first()
        if not user:
            user = Client.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            if isinstance(user, Employee):
                session['role'] = user.role
            else:
                session['role'] = 'client'
            return redirect(url_for('main.index'))
        else:
            flash("Неверный email или пароль", "error")
    return render_template('login.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    """Обрабатывает регистрацию пользователя."""
    if request.method == 'POST':
        last_name = request.form.get('last_name') or ''
        first_name = request.form.get('first_name') or ''
        middle_name = request.form.get('middle_name') or ''
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        role = request.form.get('role')
        hashed_password = generate_password_hash(password)
        name = f"{last_name} {first_name} {middle_name}".strip()
        if role == 'client':
            new_client = Client(
                name=name,
                email=email,
                phone=phone,
                password=hashed_password,
                last_name=last_name,
                first_name=first_name,
                middle_name=middle_name
            )
            db.session.add(new_client)
        else:
            new_employee = Employee(
                name=name,
                email=email,
                phone=phone,
                password=hashed_password,
                role=role
            )
            db.session.add(new_employee)
        db.session.commit()
        flash("Регистрация прошла успешно", "success")
        return redirect(url_for('main.login'))
    return render_template('register.html')

@main.route('/client_dashboard')
def client_dashboard():
    """Обрабатывает панель клиента."""
    if 'role' in session and session['role'] == 'client':
        user = Client.query.get(session['user_id'])
        if user:
            user_orders = Order.query.filter_by(client_id=session['user_id']).all()
            return render_template('client/client_dashboard.html', user=user, orders=user_orders)
        else:
            flash("Клиент не найден", "error")
            return redirect(url_for('main.login'))
    else:
        flash("Доступ запрещен. Пожалуйста, войдите как клиент.", "error")
        return redirect(url_for('main.login'))

@main.route('/appointment_success/<int:order_id>')
def appointment_success(order_id):
    """Обрабатывает успешную запись."""
    return render_template('client/appointment_success.html', order_id=order_id)

@main.route('/appointments', methods=['GET', 'POST'])
def appointments():
    """Обрабатывает запись на услугу."""
    if 'role' in session and session['role'] == 'client':
        car_form = CarForm()
        selected_service_ids = session.get('selected_services', [])
        if not selected_service_ids:
            flash("Выберите услуги на странице выбора услуг", "error")
            return redirect(url_for('main.select_services'))
        if request.method == 'POST' and car_form.validate_on_submit():
            try:
                car_model = CarModel.query.get(car_form.car_model.data)
                if not car_model:
                    flash("Модель автомобиля не найдена", "error")
                    return redirect(url_for('main.appointments'))
                new_car = Car(
                    client_id=session['user_id'],
                    car_model_id=car_model.id,
                    car_year=car_form.car_year.data,
                    vin=car_form.vin.data,
                    license_plate=car_form.license_plate.data
                )
                db.session.add(new_car)
                db.session.commit()
                end_time = calculate_end_time(car_form.appointment_time.data, selected_service_ids)
                new_order = Order(
                    client_id=session['user_id'],
                    car_id=new_car.id,
                    car_brand=car_model.brand,
                    car_model=car_model.model_name,
                    appointment_date=car_form.appointment_date.data,
                    appointment_time=car_form.appointment_time.data,
                    end_time=end_time
                )
                db.session.add(new_order)
                db.session.commit()
                for service_id in selected_service_ids:
                    service = Service.query.get(service_id)
                    if service:
                        new_order.services.append(service)
                create_task_for_order(new_order.id, get_available_mechanic().id)
                db.session.commit()
                flash("Запись успешно создана!", "success")
                return redirect(url_for('main.appointment_success', order_id=new_order.id))
            except Exception as e:
                db.session.rollback()
                flash(f"Ошибка при создании записи: {str(e)}", "error")
                return redirect(url_for('main.appointments'))
        today = datetime.now().date()
        selected_date = request.form.get('appointment_date', today)
        available_slots = get_available_slots_for_date(selected_date, selected_service_ids)
        return render_template(
            'client/appointments.html',
            available_slots=available_slots,
            car_form=car_form,
            today=today,
            selected_date=selected_date,
            selected_service_ids=selected_service_ids
        )
    return redirect(url_for('main.index'))

@main.route('/get_available_slots', methods=['POST'])
def get_available_slots():
    """Обрабатывает получение доступных слотов."""
    data = request.json
    selected_date = data.get('date')
    selected_service_ids = data.get('services', [])
    available_slots = get_available_slots_for_date(selected_date, selected_service_ids)
    return jsonify(available_slots)

@main.route('/order_details/<int:order_id>')
def order_details(order_id):
    """Обрабатывает детали заказа."""
    if 'role' in session and session['role'] == 'client':
        order = Order.query.get(order_id)
        if not order:
            flash("Заказ не найден", "error")
            return redirect(url_for('main.client_dashboard'))
        return render_template('client/order_details.html', order=order)
    return redirect(url_for('main.index'))

@main.route('/select_services', methods=['GET', 'POST'])
def select_services():
    """Обрабатывает выбор услуг."""
    form = SelectServicesForm()
    if 'role' in session and session['role'] == 'client':
        if form.validate_on_submit():
            selected_services = request.form.getlist('services')
            if not selected_services:
                flash("Выберите хотя бы одну услугу", "error")
                return redirect(url_for('main.select_services'))
            session['selected_services'] = selected_services
            return redirect(url_for('main.appointments'))
        return render_template('client/select_services.html', form=form)
    return redirect(url_for('main.index'))

@main.route('/order_history')
def order_history():
    """Обрабатывает историю заказов."""
    if 'role' in session and session['role'] == 'client':
        user = Client.query.get(session['user_id'])
        order_history = OrderHistory.query.filter_by(client_id=user.id).all()
        return render_template('client/order_history.html', user=user, order_history=order_history)
    return redirect(url_for('main.index'))

@main.route('/book_service', methods=['POST'])
def book_service():
    """Обрабатывает запись на услугу."""
    if 'role' in session and session['role'] == 'client':
        service_id = request.form.get('service_id')
        if service_id:
            flash("Вы успешно записались на ремонт!", "success")
        else:
            flash("Ошибка при записи на ремонт.", "error")
        return redirect(url_for('main.client_dashboard'))
    return redirect(url_for('main.index'))

@main.route('/mechanic_dashboard')
def mechanic_dashboard():
    """Обрабатывает панель механика."""
    if 'role' in session and session['role'] == 'mechanic':
        mechanic_id = session['user_id']
        tasks = Task.query.filter_by(employee_id=mechanic_id).all()
        return render_template('employee/mechanic/mechanic_dashboard.html', tasks=tasks)
    return redirect(url_for('main.index'))

@main.route('/mechanic_orders_current_month')
def mechanic_orders_current_month():
    """Обрабатывает заказы механика за текущий месяц."""
    if 'role' in session and session['role'] == 'mechanic':
        mechanic_id = session['user_id']
        today = datetime.now().date()
        first_day_of_month = today.replace(day=1)
        last_day_of_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        orders = (
            Order.query
            .join(Task, Order.id == Task.order_id)
            .filter(
                Task.employee_id == mechanic_id,
                Order.appointment_date >= first_day_of_month,
                Order.appointment_date <= last_day_of_month
            )
            .order_by(Order.appointment_date, Order.appointment_time)
            .all()
        )
        return render_template('employee/mechanic/mechanic_tasks_current_month.html', orders=orders)
    return redirect(url_for('main.index'))

@main.route('/task_details/<int:task_id>')
def task_details(task_id):
    """Обрабатывает подробности задачи."""
    if 'role' in session and session['role'] == 'mechanic':
        task = Task.query.get(task_id)
        if not task:
            flash("Задача не найдена", "error")
            return redirect(url_for('main.mechanic_dashboard'))
        return render_template('employee/mechanic/task_details.html', task=task)
    return redirect(url_for('main.index'))

@main.route('/generate_report')
def generate_report():
    """Обрабатывает генерацию отчета."""
    if 'role' in session and session['role'] == 'mechanic':
        mechanic_id = session['user_id']
        today = datetime.now().date()
        first_day_of_month = today.replace(day=1)
        last_day_of_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        completed_orders = (
            Order.query
            .join(Task, Order.id == Task.order_id)
            .filter(
                Task.employee_id == mechanic_id,
                Task.status == 'completed',
                Order.appointment_date >= first_day_of_month,
                Order.appointment_date <= last_day_of_month
            )
            .order_by(Order.appointment_date, Order.appointment_time)
            .all()
        )
        report_data = []
        total_revenue = 0
        for order in completed_orders:
            order_total = sum(service.price for service in order.services)
            report_data.append({
                'order_id': order.id,
                'date': order.appointment_date,
                'client': order.client.name,
                'services': ', '.join([service.service_name for service in order.services]),
                'total': order_total
            })
            total_revenue += order_total
        return render_template('employee/mechanic/report.html', report_data=report_data, total_revenue=total_revenue)
    return redirect(url_for('main.index'))

@main.route('/update_task_status/<int:task_id>', methods=['POST'])
def update_task_status(task_id):
    """Обрабатывает обновление статуса задачи."""
    if 'role' in session and session['role'] == 'mechanic':
        task = Task.query.get(task_id)
        if task:
            new_status = request.form.get('status')
            logging.debug(f"Обновление статуса задачи {task_id} на {new_status}")
            task.status = new_status
            db.session.commit()
            flash("Статус задачи обновлен", "success")
        else:
            logging.debug(f"Задача {task_id} не найдена")
            flash("Задача не найдена", "error")
        return redirect(url_for('main.mechanic_dashboard'))
    return redirect(url_for('main.index'))

@main.route('/mechanic_all_orders')
def mechanic_all_orders():
    """Обрабатывает все задачи механика."""
    if 'role' in session and session['role'] == 'mechanic':
        mechanic_id = session['user_id']
        tasks = Task.query.filter_by(employee_id=mechanic_id).all()
        return render_template('employee/mechanic/mechanic_all_orders.html', tasks=tasks)
    return redirect(url_for('main.index'))

@main.route('/mechanic_statistics')
def mechanic_statistics():
    """Обрабатывает статистику механика."""
    if 'role' in session and session['role'] == 'mechanic':
        user = Employee.query.get(session['user_id'])
        return render_template('employee/mechanic/mechanic_statistics.html', user=user)
    return redirect(url_for('main.index'))

@main.route('/mechanic_tasks_current_month')
def mechanic_tasks_current_month():
    """Обрабатывает задачи механика за текущий месяц."""
    if 'role' in session and session['role'] == 'mechanic':
        user = Employee.query.get(session['user_id'])
        today = datetime.now().date()
        first_day_of_month = today.replace(day=1)
        last_day_of_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        tasks = Task.query.filter(
            Task.employee_id == session['user_id'],
            Task.created_at >= first_day_of_month,
            Task.created_at <= last_day_of_month
        ).all()
        return render_template('employee/mechanic/mechanic_tasks_current_month.html', user=user, tasks=tasks)
    return redirect(url_for('main.index'))

@main.route('/manager_dashboard')
def manager_dashboard():
    """Обрабатывает панель менеджера."""
    if 'role' in session and session['role'] == 'manager':
        user = Employee.query.get(session['user_id'])
        employees = Employee.query.filter(Employee.role.in_(['mechanic', 'manager'])).all()
        services = Service.query.all()
        return render_template('employee/manager/manager_dashboard.html', user=user, employees=employees, services=services)
    return redirect(url_for('main.index'))

@main.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    """Обрабатывает редактирование профиля."""
    if 'role' in session:
        user = get_current_user()
        if request.method == 'POST':
            user.name = request.form['name']
            user.email = request.form['email']
            user.phone = request.form['phone']
            if request.form['password']:
                user.password = generate_password_hash(request.form['password'])
            if 'avatar' in request.files:
                file = request.files['avatar']
                if file.filename != '':
                    filename = secure_filename(file.filename)
                    file.save(os.path.join('static/avatars', filename))
                    user.avatar = filename
            db.session.commit()
            flash("Профиль обновлен!", "success")
            return redirect(url_for('main.index'))
        return render_template('edit_profile.html', user=user)
    return redirect(url_for('main.index'))

@main.route('/view_orders')
def view_orders():
    """Обрабатывает просмотр заказов."""
    if 'role' in session and session['role'] == 'manager':
        orders = Order.query.all()
        return render_template('employee/manager/view_orders.html', orders=orders)
    return redirect(url_for('main.index'))

@main.route('/generate_order_pdf/<int:order_id>')
def generate_order_pdf(order_id):
    """Обрабатывает генерацию PDF заказа."""
    order = Order.query.get(order_id)
    if not order:
        return "Заказ не найден", 404
    try:
        buffer = generate_pdf(order)
    except ValueError as e:
        return str(e), 400
    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename=order_{order_id}.pdf"
    return response

@main.route('/logout')
def logout():
    """Обрабатывает выход пользователя."""
    session.pop('user_id', None)
    session.pop('role', None)
    session.pop('selected_services', None)
    session.pop('appointment_time', None)
    session.pop('appointment_date', None)
    return redirect(url_for('main.index'))

@main.route('/tasks')
def tasks():
    """Обрабатывает задачи механика."""
    if 'role' in session and session['role'] == 'mechanic':
        employee_id = session['user_id']
        tasks = Task.query.filter_by(employee_id=employee_id).all()
        return render_template('employee/mechanic/tasks.html', tasks=tasks)
    return redirect(url_for('main.index'))

@main.route('/reports')
def reports():
    """Обрабатывает генерацию отчетов."""
    if 'role' in session and session['role'] == 'manager':
        try:
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            report = generate_manager_report(start_date, end_date)
            return render_template('employee/manager/reports.html', **report)
        except Exception as e:
            logging.error(f"Error in reports: {e}")
            return render_template('500.html'), 500
    return redirect(url_for('main.index'))

@main.route('/export_report')
def export_report():
    """Экспортирует отчет в PDF."""
    try:
        report = generate_manager_report()
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(50, 750, "Общий отчет менеджера")
        pdf.setFont("Helvetica", 12)
        pdf.drawString(50, 720, f"Общее количество заказов: {report['total_orders']}")
        pdf.drawString(50, 700, f"Общий доход: {report['total_revenue']} руб.")
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, 670, "Статистика по моделям автомобилей")
        data = [["Марка", "Модель", "Количество заказов"]]
        for item in report['orders_by_model']:
            data.append([item.brand, item.model_name, str(item.order_count)])
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        table.wrapOn(pdf, 400, 200)
        table.drawOn(pdf, 50, 550)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, 500, "Финансовые показатели по услугам")
        data = [["Услуга", "Доход (руб.)"]]
        for item in report['revenue_by_service']:
            data.append([item.service_name, str(item.revenue)])
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        table.wrapOn(pdf, 400, 200)
        table.drawOn(pdf, 50, 350)
        pdf.showPage()
        pdf.save()
        buffer.seek(0)
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename=manager_report.pdf'
        return response
    except Exception as e:
        logging.error(f"Error in export_report: {e}")
        return render_template('500.html'), 500

@main.errorhandler(404)
def page_not_found(e):
    """Обрабатывает ошибку 404."""
    return render_template('404.html'), 404

@main.errorhandler(500)
def internal_server_error(e):
    """Обрабатывает ошибку 500."""
    db.session.rollback()
    return render_template('500.html'), 500

@main.route('/manage_employees', methods=['GET', 'POST'])
def manage_employees():
    """Обрабатывает управление сотрудниками."""
    if 'role' in session and session['role'] == 'manager':
        if request.method == 'POST':
            if 'add_employee' in request.form:
                name = request.form.get('name')
                email = request.form.get('email')
                phone = request.form.get('phone')
                password = request.form.get('password')
                role = request.form.get('role')
                existing_employee = Employee.query.filter_by(email=email).first()
                if existing_employee:
                    flash("Сотрудник с таким email уже существует", "error")
                    return redirect(url_for('main.manage_employees'))
                if password is None:
                    flash("Пароль не может быть пустым", "error")
                    return redirect(url_for('main.manage_employees'))
                hashed_password = generate_password_hash(password)
                new_employee = Employee(name=name, email=email, phone=phone, password=hashed_password, role=role)
                db.session.add(new_employee)
                db.session.commit()
                flash("Сотрудник успешно добавлен", "success")
            elif 'edit_employee' in request.form:
                employee_id = request.form.get('employee_id')
                name = request.form.get('name')
                email = request.form.get('email')
                phone = request.form.get('phone')
                password = request.form.get('password')
                role = request.form.get('role')
                employee = Employee.query.get(employee_id)
                if employee:
                    if email != employee.email:
                        existing_employee = Employee.query.filter_by(email=email).first()
                        if existing_employee:
                            flash("Сотрудник с таким email уже существует", "error")
                            return redirect(url_for('main.manage_employees'))
                    employee.name = name
                    employee.email = email
                    employee.phone = phone
                    employee.role = role
                    if password is not None:
                        hashed_password = generate_password_hash(password)
                        employee.password = hashed_password
                    db.session.commit()
                    flash("Сотрудник успешно отредактирован", "success")
                else:
                    flash("Сотрудник не найден", "error")
            elif 'delete_employee' in request.form:
                employee_id = request.form.get('employee_id')
                employee = Employee.query.get(employee_id)
                if employee:
                    db.session.delete(employee)
                    db.session.commit()
                    flash("Сотрудник успешно удален", "success")
                else:
                    flash("Сотрудник не найден", "error")
        employees = Employee.query.filter(Employee.role.in_(['mechanic', 'manager'])).all()
        return render_template('employee/manager/manage_employees.html', employees=employees)
    return redirect(url_for('main.index'))

@main.route('/manage_services', methods=['GET', 'POST'])
def manage_services():
    """Обрабатывает управление услугами."""
    if 'role' in session and session['role'] == 'manager':
        if request.method == 'POST':
            if 'add_service' in request.form:
                service_name = request.form.get('service_name')
                description = request.form.get('description')
                price = request.form.get('price')
                duration = request.form.get('duration')
                if service_name is None or price is None or duration is None:
                    flash("Все поля должны быть заполнены", "error")
                    return redirect(url_for('main.manage_services'))
                new_service = Service(service_name=service_name, description=description, price=price, duration=duration)
                db.session.add(new_service)
                db.session.commit()
                flash("Услуга успешно добавлена", "success")
            elif 'edit_service' in request.form:
                service_id = request.form.get('service_id')
                service_name = request.form.get('service_name')
                description = request.form.get('description')
                price = request.form.get('price')
                duration = request.form.get('duration')
                service = Service.query.get(service_id)
                if service:
                    if service_name is not None:
                        service.service_name = service_name
                    if description is not None:
                        service.description = description
                    if price is not None:
                        service.price = price
                    if duration is not None:
                        service.duration = duration
                    db.session.commit()
                    flash("Услуга успешно отредактирована", "success")
                else:
                    flash("Услуга не найдена", "error")
            elif 'delete_service' in request.form:
                service_id = request.form.get('service_id')
                service = Service.query.get(service_id)
                if service:
                    db.session.delete(service)
                    db.session.commit()
                    flash("Услуга успешно удалена", "success")
                else:
                    flash("Услуга не найдена", "error")
        services = Service.query.all()
        return render_template('employee/manager/manage_services.html', services=services)
    return redirect(url_for('main.index'))

@main.route('/manage_car_models', methods=['GET', 'POST'])
def manage_car_models():
    """Управление списком автомобилей."""
    if 'role' in session and session['role'] == 'manager':
        if request.method == 'POST':
            if 'add_model' in request.form:
                model_name = request.form.get('model_name')
                brand = request.form.get('brand')
                new_model = CarModel(model_name=model_name, brand=brand)
                db.session.add(new_model)
                db.session.commit()
                flash("Модель успешно добавлена", "success")
            elif 'edit_model' in request.form:
                model_id = request.form.get('model_id')
                model_name = request.form.get('model_name')
                brand = request.form.get('brand')
                model = CarModel.query.get(model_id)
                if model:
                    model.model_name = model_name
                    model.brand = brand
                    db.session.commit()
                    flash("Модель успешно отредактирована", "success")
                else:
                    flash("Модель не найдена", "error")
            elif 'delete_model' in request.form:
                model_id = request.form.get('model_id')
                model = CarModel.query.get(model_id)
                if model:
                    db.session.delete(model)
                    db.session.commit()
                    flash("Модель успешно удалена", "success")
                else:
                    flash("Модель не найдена", "error")
        car_models = CarModel.query.all()
        return render_template('manage_car_models.html', car_models=car_models)
    return redirect(url_for('main.index'))

@main.route('/generate_full_report')
def generate_full_report():
    """Обрабатывает генерацию отчета за все время."""
    if 'role' in session and session['role'] == 'mechanic':
        mechanic_id = session['user_id']
        completed_orders = (
            Order.query
            .join(Task, Order.id == Task.order_id)
            .filter(
                Task.employee_id == mechanic_id,
                Task.status == 'completed'
            )
            .order_by(Order.appointment_date, Order.appointment_time)
            .all()
        )
        report_data = []
        total_revenue = 0
        for order in completed_orders:
            order_total = sum(service.price for service in order.services)
            report_data.append({
                'order_id': order.id,
                'date': order.appointment_date,
                'client': order.client.name,
                'services': ', '.join([service.service_name for service in order.services]),
                'total': order_total
            })
            total_revenue += order_total
        return render_template('employee/mechanic/report.html', report_data=report_data, total_revenue=total_revenue)
    return redirect(url_for('main.index'))

@main.route('/manage_clients', methods=['GET', 'POST'])
def manage_clients():
    """Обрабатывает управление клиентами."""
    if 'role' in session and session['role'] == 'manager':
        if request.method == 'POST':
            if 'add_client' in request.form:
                last_name = request.form.get('last_name')
                first_name = request.form.get('first_name')
                middle_name = request.form.get('middle_name')
                email = request.form.get('email')
                phone = request.form.get('phone')
                password = request.form.get('password')
                if not last_name or not first_name or not email or not phone or not password:
                    flash("Все поля обязательны для заполнения", "error")
                    return redirect(url_for('main.manage_clients'))
                existing_client = Client.query.filter_by(email=email).first()
                if existing_client:
                    flash("Клиент с таким email уже существует", "error")
                    return redirect(url_for('main.manage_clients'))
                hashed_password = generate_password_hash(password)
                new_client = Client(
                    last_name=last_name,
                    first_name=first_name,
                    middle_name=middle_name,
                    email=email,
                    phone=phone,
                    password=hashed_password,
                    name=f"{last_name} {first_name} {middle_name}".strip()
                )
                db.session.add(new_client)
                db.session.commit()
                flash("Клиент успешно добавлен", "success")
            elif 'edit_client' in request.form:
                client_id = request.form.get('client_id')
                last_name = request.form.get('last_name')
                first_name = request.form.get('first_name')
                middle_name = request.form.get('middle_name')
                email = request.form.get('email')
                phone = request.form.get('phone')
                password = request.form.get('password')
                client = Client.query.get(client_id)
                if client:
                    if not last_name or not first_name or not email or not phone:
                        flash("Все поля обязательны для заполнения", "error")
                        return redirect(url_for('main.manage_clients'))
                    if email != client.email:
                        existing_client = Client.query.filter_by(email=email).first()
                        if existing_client:
                            flash("Клиент с таким email уже существует", "error")
                            return redirect(url_for('main.manage_clients'))
                    client.last_name = last_name
                    client.first_name = first_name
                    client.middle_name = middle_name
                    client.email = email
                    client.phone = phone
                    client.name = f"{last_name} {first_name} {middle_name}".strip()
                    if password is not None:
                        hashed_password = generate_password_hash(password)
                        client.password = hashed_password
                    db.session.commit()
                    flash("Клиент успешно отредактирован", "success")
                else:
                    flash("Клиент не найден", "error")
            elif 'delete_client' in request.form:
                client_id = request.form.get('client_id')
                client = Client.query.get(client_id)
                if client:
                    db.session.delete(client)
                    db.session.commit()
                    flash("Клиент успешно удален", "success")
                else:
                    flash("Клиент не найден", "error")
        clients = Client.query.all()
        return render_template('employee/manager/manage_clients.html', clients=clients)
    return redirect(url_for('main.index'))

@main.route('/delete_appointment/<int:appointment_id>', methods=['POST'])
def delete_appointment(appointment_id):
    """Обрабатывает удаление записи."""
    if 'role' in session and session['role'] == 'manager':
        appointment = Order.query.get(appointment_id)
        if appointment:
            db.session.delete(appointment)
            db.session.commit()
            flash("Запись успешно удалена", "success")
        else:
            flash("Запись не найдена", "error")
        return redirect(url_for('main.manage_appointments'))
    return redirect(url_for('main.index'))

@main.route('/manage_appointments')
def manage_appointments():
    """Обрабатывает управление записями."""
    if 'role' in session and session['role'] == 'manager':
        appointments = Order.query.all()
        return render_template('employee/manager/manage_appointments.html', appointments=appointments)
    return redirect(url_for('main.index'))

@main.route('/statistics')
def statistics():
    """Статистика и аналитика."""
    if 'role' in session and session['role'] == 'manager':
        stats = calculate_statistics()
        return render_template('statistics.html', **stats)
    return redirect(url_for('main.index'))
