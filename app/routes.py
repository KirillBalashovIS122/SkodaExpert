from flask import Blueprint, render_template, request, redirect, url_for, session, make_response, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from .models import Employee, Client, Car, Service, Order, Task, Report, AppointmentSlot, OrderHistory
from . import db, csrf
from .utils import get_current_user, generate_pdf, calculate_statistics
from .forms import SelectServicesForm  # Импортируем форму
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
        last_name = request.form.get('last_name')
        first_name = request.form.get('first_name')
        middle_name = request.form.get('middle_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        role = request.form.get('role')
        hashed_password = generate_password_hash(password)
        new_employee = Employee(last_name=last_name, first_name=first_name, middle_name=middle_name, email=email, phone=phone, password=hashed_password, role=role)
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

@main.route('/mechanic_dashboard')
def mechanic_dashboard():
    if 'role' in session and session['role'] == 'mechanic':
        user = Employee.query.get(session['user_id'])
        today = datetime.now().date()
        next_week = today + timedelta(days=7)
        tasks = Task.query.filter(
            Task.employee_id == session['user_id'],
            Task.created_at >= today,
            Task.created_at < next_week
        ).all()
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
            full_name = request.form.get('full_name')
            car_model = request.form.get('car_model')
            vin_number = request.form.get('car_vin')
            car_plate = request.form.get('car_plate')
            phone = request.form.get('phone')
            car_year = request.form.get('car_year')
            appointment_date = request.form.get('appointment_date')
            appointment_time = request.form.get('appointment_time')

            if 'user_id' not in session:
                return jsonify({'success': False, 'error': 'User ID not found in session'}), 400

            client = Client.query.get(session['user_id'])
            if not client:
                return jsonify({'success': False, 'error': 'Client not found'}), 400

            try:
                car = create_car(client.id, car_model, vin_number, car_plate, car_year)
                new_order = create_order(client.id, car.id, appointment_date, appointment_time)
                save_order_history(new_order.id, client.id, car.id)
                return redirect(url_for('main.appointment_success', order_id=new_order.id))
            except ValueError as e:
                db.session.rollback()
                return jsonify({'success': False, 'error': str(e)}), 400
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error creating order: {e}")
                return jsonify({'success': False, 'error': 'Error creating order'}), 500

        if 'selected_services' not in session:
            return redirect(url_for('main.select_services'))

        today = datetime.now().date()
        available_slots = get_available_slots(today)

        selected_services = session.get('selected_services', [])
        services = Service.query.all()

        return render_template('client/appointments.html', available_slots=available_slots, services=services, selected_services=selected_services)

    return redirect(url_for('main.index'))

@main.route('/get_available_slots', methods=['GET'])
def get_available_slots():
    date_str = request.args.get('date')
    date = datetime.strptime(date_str, '%Y-%m-%d').date()
    slots = get_available_slots(date)
    return jsonify(slots)

def get_available_slots(date):
    # Get all slots for the given date
    slots = AppointmentSlot.query.filter(
        AppointmentSlot.appointment_date == date,
        AppointmentSlot.is_available == True
    ).all()

    # Filter out slots that are already booked
    booked_slots = Order.query.filter(
        Order.appointment_date == date
    ).all()

    booked_times = []
    for order in booked_slots:
        services = order.services
        total_duration = sum(service.duration for service in services)
        start_time = datetime.strptime(order.appointment_time, '%H:%M').time()
        end_time = (datetime.combine(date, start_time) + timedelta(minutes=total_duration)).time()
        booked_times.append((start_time, end_time))

    available_slots = []
    for slot in slots:
        slot_start_time = slot.start_time.time()
        slot_end_time = slot.end_time.time()
        if not any(start <= slot_start_time < end or start < slot_end_time <= end for start, end in booked_times):
            available_slots.append(slot)

    return available_slots

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

@main.route('/reports', methods=['GET', 'POST'])
def reports():
    if 'role' in session and session['role'] == 'mechanic':
        if request.method == 'POST':
            task_id = request.form.get('task_id')
            description = request.form.get('description')
            new_report = Report(task_id=task_id, description=description)
            db.session.add(new_report)
            db.session.commit()
            return redirect(url_for('main.tasks'))
        return render_template('employee/mechanic/reports.html')
    return redirect(url_for('main.index'))

@main.route('/manage_employees', methods=['GET', 'POST'])
def manage_employees():
    if 'role' in session and session['role'] == 'manager':
        if request.method == 'POST':
            last_name = request.form.get('last_name')
            first_name = request.form.get('first_name')
            middle_name = request.form.get('middle_name')
            role = request.form.get('role')
            email = request.form.get('email')
            password = request.form.get('password')
            hashed_password = generate_password_hash(password)
            new_employee = Employee(last_name=last_name, first_name=first_name, middle_name=middle_name, role=role, email=email, password=hashed_password)
            db.session.add(new_employee)
            db.session.commit()
            return redirect(url_for('main.manage_employees'))
        employees = Employee.query.filter(Employee.role.in_(['mechanic', 'manager'])).all()
        return render_template('employee/manager/manage_employees.html', employees=employees)
    return redirect(url_for('main.index'))

@main.route('/manage_services', methods=['GET', 'POST'])
def manage_services():
    if 'role' in session and session['role'] == 'manager':
        if request.method == 'POST':
            service_name = request.form.get('service_name')
            description = request.form.get('description')
            price = request.form.get('price')
            duration = request.form.get('duration')
            new_service = Service(service_name=service_name, description=description, price=price, duration=duration)
            db.session.add(new_service)
            db.session.commit()
            return redirect(url_for('main.manage_services'))
        services = Service.query.all()
        return render_template('employee/manager/manage_services.html', services=services)
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