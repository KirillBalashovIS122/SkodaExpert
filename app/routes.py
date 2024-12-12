from flask import Blueprint, render_template, request, redirect, url_for, session, make_response, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, time, date
from .models import *
from . import db, csrf
from .utils import *
from .forms import SelectServicesForm, CarForm
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.DEBUG)

main = Blueprint('main', __name__)

@main.route('/')
def index():
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
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = Employee.query.filter_by(email=email).first() or Client.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role if isinstance(user, Employee) else 'client'
            return redirect(url_for('main.index'))
        else:
            flash("Неверный email или пароль", "error")
    return render_template('login.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
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
        
        new_employee = Employee(name=name, email=email, phone=phone, password=hashed_password, role=role)
        db.session.add(new_employee)
        db.session.commit()
        flash("Регистрация прошла успешно", "success")
        return redirect(url_for('main.login'))
    return render_template('register.html')

@main.route('/client_dashboard')
def client_dashboard():
    if 'role' in session and session['role'] == 'client':
        user = Client.query.get(session['user_id'])
        user_orders = Order.query.filter_by(client_id=session['user_id']).all()
        services = Service.query.all()
        return render_template('client/client_dashboard.html', user=user, orders=user_orders, services=services)
    return redirect(url_for('main.index'))

@main.route('/mechanic_dashboard', methods=['GET'])
def mechanic_dashboard():
    if 'role' in session and session['role'] == 'mechanic':
        mechanic_id = session['user_id']
        logging.debug(f"Mechanic dashboard accessed by user ID: {mechanic_id}")
        tasks = get_mechanic_tasks(mechanic_id)
        logging.debug(f"Fetched tasks: {tasks}")  # Логируем задачи
        return render_template('employee/mechanic/mechanic_dashboard.html', tasks=tasks)
    return redirect(url_for('main.index'))

def create_task_for_order(order_id, employee_id):
    logging.debug(f"Creating task for order ID: {order_id}, employee ID: {employee_id}")
    new_task = Task(
        employee_id=employee_id,
        order_id=order_id,
        status='pending'
    )
    db.session.add(new_task)
    db.session.commit()
    logging.debug(f"Task created: {new_task}")

@main.route('/mechanic_orders_current_month')
def mechanic_orders_current_month():
    if 'role' in session and session['role'] == 'mechanic':
        mechanic_id = session['user_id']
        today = datetime.now().date()
        first_day_of_month = today.replace(day=1)
        last_day_of_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        # Получаем заказы механика за текущий месяц
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
    if 'role' in session and session['role'] == 'mechanic':
        task = Task.query.get(task_id)
        if not task:
            flash("Задача не найдена", "error")
            return redirect(url_for('main.mechanic_dashboard'))
        return render_template('employee/mechanic/task_details.html', task=task)
    return redirect(url_for('main.index'))

@main.route('/generate_report')
def generate_report():
    if 'role' in session and session['role'] == 'mechanic':
        mechanic_id = session['user_id']
        today = datetime.now().date()
        first_day_of_month = today.replace(day=1)
        last_day_of_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        # Получаем выполненные заказы механика за текущий месяц
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

        # Генерируем отчет
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
    if 'role' in session and session['role'] == 'mechanic':
        task = Task.query.get(task_id)
        if task:
            new_status = request.form.get('status')
            task.status = new_status
            db.session.commit()
            flash("Статус задачи обновлен", "success")
        else:
            flash("Задача не найдена", "error")
        return redirect(url_for('main.mechanic_dashboard'))
    return redirect(url_for('main.index'))

@main.route('/mechanic_all_orders')
def mechanic_all_orders():
    if 'role' in session and session['role'] == 'mechanic':
        user = Employee.query.get(session['user_id'])
        tasks = Task.query.filter_by(employee_id=session['user_id']).all()
        return render_template('employee/mechanic/tasks.html', user=user, tasks=tasks)
    return redirect(url_for('main.index'))

@main.route('/mechanic_statistics')
def mechanic_statistics():
    if 'role' in session and session['role'] == 'mechanic':
        user = Employee.query.get(session['user_id'])
        # Ваш код для получения статистики
        return render_template('employee/mechanic/mechanic_statistics.html', user=user, tasks=tasks)
    return redirect(url_for('main.index'))

@main.route('/mechanic_tasks_current_month')
def mechanic_tasks_current_month():
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
    if 'role' in session and session['role'] == 'manager':
        user = Employee.query.get(session['user_id'])
        employees = Employee.query.filter(Employee.role.in_(['mechanic', 'manager'])).all()
        services = Service.query.all()
        return render_template('employee/manager/manager_dashboard.html', user=user, employees=employees, services=services)
    return redirect(url_for('main.index'))

@main.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'role' in session:
        user = get_current_user()
        if request.method == 'POST':
            user.last_name = request.form['last_name']
            user.first_name = request.form['first_name']
            user.middle_name = request.form['middle_name']
            user.email = request.form['email']
            user.phone = request.form['phone']
            db.session.commit()
            flash("Профиль обновлен!", "success")
            return redirect(url_for('main.index'))
        return render_template('edit_profile.html', user=user)
    return redirect(url_for('main.index'))

@main.route('/appointment_success/<int:order_id>')
def appointment_success(order_id):
    return render_template('client/appointment_success.html', order_id=order_id)

@main.route('/appointments', methods=['GET', 'POST'])
def appointments():
    if 'role' in session and session['role'] == 'client':
        car_form = CarForm()
        selected_service_ids = session.get('selected_services', [])

        if not selected_service_ids:
            flash("Выберите услуги на странице выбора услуг", "error")
            return redirect(url_for('main.select_services'))

        if request.method == 'POST' and car_form.validate_on_submit():
            appointment_date = request.form.get('appointment_date')
            appointment_time = request.form.get('appointment_time')

            try:
                appointment_datetime = datetime.strptime(f"{appointment_date} {appointment_time}", '%Y-%m-%d %H:%M')
            except ValueError as e:
                logging.error(f"Error parsing datetime: {e}")
                flash("Неверный формат даты и времени", "error")
                return redirect(url_for('main.appointments'))

            # Проверяем доступность времени
            available_slots = get_available_slots_for_date(appointment_datetime.date(), selected_service_ids)
            if not any(slot == appointment_time and is_available for slot, is_available in available_slots):
                flash("Выбранное время уже занято. Пожалуйста, выберите другое время.", "error")
                return redirect(url_for('main.appointments'))

            # Проверка на валидность даты и времени
            if not is_valid_appointment_date(appointment_datetime.date(), appointment_time):
                flash("Нельзя записаться на прошедшее время или после 17:00.", "error")
                return redirect(url_for('main.appointments'))

            try:
                new_order = Order(
                    client_id=session['user_id'],
                    appointment_date=appointment_datetime.date(),
                    appointment_time=appointment_time
                )
                db.session.add(new_order)
                db.session.commit()

                # Создаем задачу для заказа
                new_task = Task(
                    employee_id=13,  # Укажите ID механика
                    order_id=new_order.id,
                    status='pending'
                )
                db.session.add(new_task)
                db.session.commit()

                for service_id in selected_service_ids:
                    service = Service.query.get(service_id)
                    if service:
                        new_order.services.append(service)
                db.session.commit()

                new_car = Car(
                    client_id=session['user_id'],
                    model=car_form.model.data,
                    car_year=car_form.car_year.data,
                    vin=car_form.vin.data,
                    license_plate=car_form.license_plate.data
                )
                db.session.add(new_car)
                db.session.commit()

                new_order.car_id = new_car.id
                db.session.commit()

                flash("Запись успешно создана!", "success")
                return redirect(url_for('main.appointment_success', order_id=new_order.id))

            except Exception as e:
                db.session.rollback()
                logging.error(f"Database error: {e}")
                flash("Ошибка при сохранении данных", "error")

        # Получаем сегодняшнюю дату
        today = datetime.now().date()

        # Получаем выбранную дату из формы (если она есть)
        selected_date = request.form.get('appointment_date', today)

        # Получаем доступные слоты для выбранной даты
        available_slots = get_available_slots_for_date(selected_date, selected_service_ids)

        return render_template(
            'client/appointments.html', 
            available_slots=available_slots, 
            car_form=car_form,
            today=today,  # Сегодняшняя дата
            selected_date=selected_date,  # Выбранная дата
            selected_service_ids=selected_service_ids
        )
    return redirect(url_for('main.index'))

@main.route('/get_available_slots', methods=['POST'])
def get_available_slots():
    # Получаем данные из запроса
    data = request.json
    selected_date = data.get('date')
    selected_service_ids = data.get('services', [])

    # Получаем доступные слоты для выбранной даты
    available_slots = get_available_slots_for_date(selected_date, selected_service_ids)

    # Возвращаем слоты в формате JSON
    return jsonify(available_slots)

def is_valid_appointment_date(date, appointment_time):
    current_time = datetime.now()
    opening_time = time(9, 0)
    closing_time = time(17, 0)

    logging.debug(f"Checking if date {date} is valid for appointment time {appointment_time}")

    # Проверка на прошедшую дату
    if date < current_time.date():
        logging.debug(f"Date {date} is in the past.")
        return False
    
    # Проверка на текущее число после закрытия
    if date == current_time.date() and current_time.time() >= closing_time:
        logging.debug(f"Current time {current_time.time()} is after closing time {closing_time}.")
        return False

    # Проверка, что время находится в пределах рабочего времени
    if datetime.strptime(appointment_time, '%H:%M').time() < opening_time or datetime.strptime(appointment_time, '%H:%M').time() >= closing_time:
        logging.debug(f"Appointment time {appointment_time} is outside working hours ({opening_time} - {closing_time}).")
        return False
    
    logging.debug(f"Date {date} is valid for appointment time {appointment_time}.")
    return True

def get_available_slots_for_date(date_str, selected_service_ids):
    # Проверяем, является ли date_str объектом datetime.date
    if isinstance(date_str, date):  # Используем импортированный класс date
        date_obj = date_str
    else:
        # Если это строка, то преобразуем её в объект datetime.date
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

    # Получаем все записи на указанную дату
    existing_orders = Order.query.filter_by(appointment_date=date_obj).all()

    # Если на указанную дату нет записей, все слоты доступны
    if not existing_orders:
        work_start = time(9, 0)
        work_end = time(17, 0)
        slot_duration = timedelta(minutes=30)
        current_time = datetime.combine(date_obj, work_start)
        available_slots = []

        while current_time.time() < work_end:
            slot_start_str = current_time.strftime('%H:%M')
            available_slots.append((slot_start_str, True))  # Все слоты доступны
            current_time += slot_duration

        return available_slots

    # Если есть записи, собираем занятые слоты
    booked_slots = {}
    for order in existing_orders:
        start_time = order.appointment_time
        end_time = order.end_time
        booked_slots[start_time.strftime('%H:%M')] = (start_time, end_time)

    logging.debug(f"Date: {date_obj}, Booked slots: {booked_slots}")

    work_start = time(9, 0)
    work_end = time(17, 0)
    slot_duration = timedelta(minutes=30)

    selected_services_objects = Service.query.filter(Service.id.in_(selected_service_ids)).all()
    total_service_duration = sum(service.duration for service in selected_services_objects)

    logging.debug(f"Total service duration for selected services: {total_service_duration} minutes")

    current_time = datetime.combine(date_obj, work_start)
    available_slots = []

    while current_time.time() < work_end:
        slot_start_str = current_time.strftime('%H:%M')
        is_available = is_slot_available(current_time.time(), total_service_duration, booked_slots)
        available_slots.append((slot_start_str, is_available))
        logging.debug(f"Slot {slot_start_str} is {'available' if is_available else 'not available'}.")
        current_time += slot_duration

    logging.debug(f"Date: {date_obj}, Available slots: {available_slots}")

    return available_slots

def is_slot_available(slot_start_time, service_duration, booked_slots):
    # Вычисляем время окончания текущего слота
    slot_end_time = (datetime.combine(datetime.today(), slot_start_time) + timedelta(minutes=service_duration)).time()
    logging.debug(f"Checking if slot {slot_start_time} - {slot_end_time} is available.")

    # Проверяем пересечение с каждым занятым слотом
    for booked_start, booked_end in booked_slots.values():
        # Если текущий слот пересекается с занятым слотом, он не доступен
        if slot_start_time < booked_end and slot_end_time > booked_start:
            logging.debug(f"Slot {slot_start_time} - {slot_end_time} overlaps with {booked_start} - {booked_end}.")
            return False

    logging.debug(f"Slot {slot_start_time} - {slot_end_time} is available.")
    return True

def create_appointment_slots(date):
    start_time = datetime.strptime('09:00', '%H:%M').time()
    end_time = datetime.strptime('17:00', '%H:%M').time()
    current_time = start_time
    while current_time < end_time:
        slot = AppointmentSlot(
            appointment_date=date,
            start_time=datetime.combine(date, current_time),
            end_time=datetime.combine(date, (datetime.combine(datetime.today(), current_time) + timedelta(minutes=30)).time()),
            is_available=True  # Устанавливаем is_available в True
        )
        db.session.add(slot)
        current_time = (datetime.combine(datetime.today(), current_time) + timedelta(minutes=30)).time()
    db.session.commit()

@main.route('/view_orders')
def view_orders():
    if 'role' in session and session['role'] == 'manager':
        orders = Order.query.all()
        return render_template('employee/manager/view_orders.html', orders=orders)
    return redirect(url_for('main.index'))

@main.route('/generate_order_pdf/<int:order_id>')
def generate_order_pdf(order_id):
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

def get_mechanic_tasks(employee_id):
    logging.debug(f"Fetching tasks for mechanic with ID: {employee_id}")
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
    logging.debug(f"Fetched tasks: {tasks}")  # Логируем задачи
    return tasks

@main.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    session.pop('selected_services', None)
    session.pop('appointment_time', None)
    session.pop('appointment_date', None)
    return redirect(url_for('main.index'))

@main.route('/tasks')
def tasks():
    if 'role' in session and session['role'] == 'mechanic':
        employee_id = session['user_id']
        tasks = Task.query.filter_by(employee_id=employee_id).all()
        return render_template('employee/mechanic/tasks.html', tasks=tasks)
    return redirect(url_for('main.index'))

@main.route('/reports')
def reports():
    if 'role' in session and session['role'] == 'manager':
        stats = calculate_statistics()
        return render_template('employee/manager/reports.html', **stats)
    return redirect(url_for('main.index'))

@main.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@main.errorhandler(500)
def internal_server_error(e):
    db.session.rollback()
    return render_template('500.html'), 500

@main.route('/manage_employees', methods=['GET', 'POST'])
def manage_employees():
    if 'role' in session and session['role'] == 'manager':
        if request.method == 'POST':
            if 'add_employee' in request.form:
                name = request.form.get('name')
                email = request.form.get('email')
                phone = request.form.get('phone')
                password = request.form.get('password')
                role = request.form.get('role')

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

@main.route('/manage_clients', methods=['GET', 'POST'])
def manage_clients():
    if 'role' in session and session['role'] == 'manager':
        if request.method == 'POST':
            if 'add_client' in request.form:
                name = request.form.get('name')
                email = request.form.get('email')
                phone = request.form.get('phone')
                password = request.form.get('password')
                hashed_password = generate_password_hash(password)
                new_client = Client(name=name, email=email, phone=phone, password=hashed_password)
                db.session.add(new_client)
                db.session.commit()
                flash("Клиент успешно добавлен", "success")
            elif 'edit_client' in request.form:
                client_id = request.form.get('client_id')
                name = request.form.get('name')
                email = request.form.get('email')
                phone = request.form.get('phone')
                password = request.form.get('password')

                client = Client.query.get(client_id)
                if client:
                    client.name = name
                    client.email = email
                    client.phone = phone
                    if password:
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
    if 'role' in session and session['role'] == 'manager':
        appointments = Order.query.all()
        return render_template('employee/manager/manage_appointments.html', appointments=appointments)
    return redirect(url_for('main.index'))

@main.route('/statistics')
def statistics():
    if 'role' in session and session['role'] == 'manager':
        stats = calculate_statistics()
        return render_template('employee/manager/statistics.html', **stats)
    return redirect(url_for('main.index'))

@main.route('/book_service', methods=['POST'])
def book_service():
    if 'role' in session and session['role'] == 'client':
        service_id = request.form.get('service_id')
        if service_id:
            flash("Вы успешно записались на ремонт!", "success")
        else:
            flash("Ошибка при записи на ремонт.", "error")
        return redirect(url_for('main.client_dashboard'))
    return redirect(url_for('main.index'))

@main.route('/select_services', methods=['GET', 'POST'])
def select_services():
    form = SelectServicesForm()
    if 'role' in session and session['role'] == 'client':
        if form.validate_on_submit():
            selected_services = request.form.getlist('services')
            if not selected_services:
                flash("Выберите хотя бы одну услугу", "error")
                return redirect(url_for('main.select_services'))
            session['selected_services'] = selected_services
            logging.debug(f"Selected services: {selected_services}")
            return redirect(url_for('main.appointments'))
        return render_template('client/select_services.html', form=form)
    return redirect(url_for('main.index'))

@main.route('/order_history')
def order_history():
    if 'role' in session and session['role'] == 'client':
        user = Client.query.get(session['user_id'])
        order_history = OrderHistory.query.filter_by(client_id=user.id).all()
        return render_template('client/order_history.html', user=user, order_history=order_history)
    return redirect(url_for('main.index'))

@main.route('/order_details/<int:order_id>')
def order_details(order_id):
    if 'role' in session and session['role'] == 'client':
        user = Client.query.get(session['user_id'])
        order = Order.query.get(order_id)
        if not order or order.client_id != user.id:
            return "Заказ не найден", 404
        return render_template('client/order_details.html', user=user, order=order)
    return redirect(url_for('main.index'))