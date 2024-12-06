from flask import Blueprint, render_template, request, redirect, url_for, session, make_response, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from .models import Employee, Client, Car, Service, Order, Task, Report, AppointmentSlot, OrderHistory
from . import db, csrf
from .utils import get_current_user, generate_pdf, calculate_statistics
from .forms import SelectServicesForm  # Импортируем форму
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
        
        # Объединяем last_name, first_name и middle_name в одну строку
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

from sqlalchemy import text

@main.route('/mechanic_dashboard')
def mechanic_dashboard():
    if 'role' in session and session['role'] == 'mechanic':
        user = Employee.query.get(session['user_id'])
        today = datetime.now().date()
        next_week = today + timedelta(days=7)
        
        query = text("""
            SELECT * FROM tasks 
            WHERE employee_id = :employee_id 
            AND created_at >= :today 
            AND created_at < :next_week
        """)
        tasks = db.session.execute(query, {
            'employee_id': session['user_id'],
            'today': today,
            'next_week': next_week
        }).fetchall()
        
        return render_template('employee/mechanic/mechanic_dashboard.html', user=user, tasks=tasks)
    return redirect(url_for('main.index'))

@main.route('/mechanic_all_orders')
def mechanic_all_orders():
    if 'role' in session and session['role'] == 'mechanic':
        user = Employee.query.get(session['user_id'])
        tasks = Task.query.filter_by(employee_id=session['user_id']).all()
        return render_template('employee/mechanic/tasks.html', user=user, tasks=tasks)
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
        if request.method == 'POST':
            appointment_date = request.form.get('appointment_date')
            appointment_time = request.form.get('appointment_time')
            selected_services = session.get('selected_services', [])
            if not appointment_date or not appointment_time or not selected_services:
                flash("Выберите дату, время и услуги", "error")
                return redirect(url_for('main.appointments'))
            
            # Создаем новый заказ
            new_order = Order(
                client_id=session['user_id'],
                appointment_date=datetime.strptime(appointment_date, '%Y-%m-%d').date(),
                appointment_time=appointment_time
            )
            db.session.add(new_order)
            db.session.commit()
            
            # Добавляем выбранные услуги к заказу
            for service_id in selected_services:
                service = Service.query.get(service_id)
                if service:
                    new_order.services.append(service)
            db.session.commit()
            
            return redirect(url_for('main.appointment_success', order_id=new_order.id))

        today = datetime.now().date()
        available_slots = get_available_slots_for_date(today)  # Исправлено здесь
        selected_services = session.get('selected_services', [])
        services = Service.query.all()
        return render_template('client/appointments.html', available_slots=available_slots, services=services, selected_services=selected_services)
    return redirect(url_for('main.index'))

@main.route('/get_available_slots', methods=['GET'])
def get_available_slots():
    date_str = request.args.get('date')
    date = datetime.strptime(date_str, '%Y-%m-%d').date()
    slots = get_available_slots_for_date(date)
    return jsonify(slots)

def get_available_slots_for_date(date):
    # Создаем временные слоты, если их еще нет
    existing_slots = AppointmentSlot.query.filter_by(appointment_date=date).all()
    if not existing_slots:
        create_appointment_slots(date)
    
    # Получаем все записи на выбранную дату
    existing_orders = Order.query.filter_by(appointment_date=date).all()
    
    # Получаем все временные слоты на выбранную дату
    appointment_slots = AppointmentSlot.query.filter_by(appointment_date=date, is_available=True).all()
    
    # Создаем словарь для хранения занятых слотов
    booked_slots = {}
    for order in existing_orders:
        start_time = datetime.strptime(order.appointment_time, '%H:%M').time()
        duration = sum(service.duration for service in order.services)
        end_time = (datetime.combine(date, start_time) + timedelta(minutes=duration)).time()
        booked_slots[order.appointment_time] = (start_time, end_time)
    
    # Создаем список доступных слотов
    available_slots = []
    for slot in appointment_slots:
        slot_start_time = slot.start_time.time()
        slot_end_time = slot.end_time.time()
        is_available = True
        for booked_start, booked_end in booked_slots.values():
            if (slot_start_time < booked_end and slot_end_time > booked_start):
                is_available = False
                break
        if is_available:
            available_slots.append(slot_start_time.strftime('%H:%M'))
    
    return available_slots

def create_appointment_slots(date):
    start_time = datetime.strptime('09:00', '%H:%M').time()
    end_time = datetime.strptime('17:00', '%H:%M').time()
    current_time = datetime.combine(date, start_time)
    
    while current_time.time() < end_time:
        slot = AppointmentSlot(
            appointment_date=date,
            start_time=current_time,
            end_time=(current_time + timedelta(minutes=30)),
            is_available=True
        )
        db.session.add(slot)
        current_time += timedelta(minutes=30)
    
    db.session.commit()

def create_car(client_id, model, vin, license_plate, car_year):
    logging.debug(f"Creating car: client_id={client_id}, model={model}, vin={vin}, license_plate={license_plate}, car_year={car_year}")
    client = Client.query.get(client_id)
    if not client:
        raise ValueError(f"Client with id {client_id} does not exist")

    if not model or not vin or not license_plate or not car_year:
        raise ValueError("All fields are required")

    new_car = Car(
        client_id=client_id,
        model=model,
        vin=vin,
        license_plate=license_plate,
        car_year=car_year
    )
    db.session.add(new_car)
    db.session.commit()
    logging.debug(f"Car created: {new_car}")
    return new_car

def create_order(client_id, car_id, appointment_date, appointment_time):
    logging.debug(f"Creating order: client_id={client_id}, car_id={car_id}")
    new_order = Order(
        client_id=client_id,
        car_id=car_id,
        appointment_date=appointment_date,
        appointment_time=appointment_time
    )
    db.session.add(new_order)
    db.session.commit()

    selected_services = session.get('selected_services', [])
    for service_id in selected_services:
        service = Service.query.get(service_id)
        if service:
            new_order.services.append(service)

    db.session.commit()
    logging.debug(f"Order created: {new_order}")
    return new_order

def save_order_history(order_id, client_id, car_id):
    logging.debug(f"Saving order history: order_id={order_id}, client_id={client_id}, car_id={car_id}")
    new_order_history = OrderHistory(order_id=order_id, client_id=client_id, car_id=car_id)
    db.session.add(new_order_history)
    db.session.commit()
    logging.debug(f"Order history saved: {new_order_history}")

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

                # Проверка на None для пароля
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

                    # Проверка на None для пароля
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

                # Проверка на None для service_name, price и duration
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
                    # Обновляем только те поля, которые были переданы
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