from flask import Blueprint, render_template, request, redirect, url_for, session, make_response, flash, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta, datetime
from .models import User, Car, Service, Order, Task, Report, AppointmentSlot, Client, OrderHistory
from . import db, csrf
from .utils import get_current_user, generate_pdf, calculate_statistics
from flask_wtf import FlaskForm
from wtforms import SubmitField
import logging

main = Blueprint('main', __name__)

class SelectServicesForm(FlaskForm):
    submit = SubmitField('Далее')

@main.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('main.client_dashboard'))
    return redirect(url_for('main.register'))

@main.route('/login', methods=['GET', 'POST'])
@csrf.exempt
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            return redirect(url_for('main.client_dashboard'))
        else:
            flash("Неверный email или пароль", "error")
    return render_template('login.html')

@main.route('/register', methods=['GET', 'POST'])
@csrf.exempt
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        role = request.form.get('role')
        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, phone=phone, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash("Регистрация прошла успешно", "success")
        return redirect(url_for('main.login'))
    return render_template('register.html')

@main.route('/client_dashboard')
def client_dashboard():
    if 'role' in session and session['role'] == 'client':
        user = User.query.get(session['user_id'])
        user_orders = Order.query.filter_by(client_id=session['user_id']).all()
        services = Service.query.all()
        return render_template('client/client_dashboard.html', user=user, orders=user_orders, services=services)
    return redirect(url_for('main.index'))

@main.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'role' in session and session['role'] == 'client':
        user = User.query.get(session['user_id'])
        if request.method == 'POST':
            user.name = request.form['name']
            user.email = request.form['email']
            user.phone = request.form['phone']
            db.session.commit()
            flash("Профиль обновлен!", "success")
            return redirect(url_for('main.client_dashboard'))
        return render_template('client/edit_profile.html', user=user)
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

            print(f"Received form data: full_name={full_name}, car_model={car_model}, vin_number={vin_number}, car_plate={car_plate}, phone={phone}, car_year={car_year}, appointment_date={appointment_date}, appointment_time={appointment_time}")

            if 'user_id' not in session:
                return jsonify({'success': False, 'error': 'User ID not found in session'}), 400

            client = User.query.get(session['user_id'])
            if not client:
                return jsonify({'success': False, 'error': 'Client not found'}), 400

            try:
                car = create_car(client.id, car_model, vin_number, car_plate, car_year)
                new_order = create_order(client.id, car.id)
                save_order_history(new_order.id, client.id, car.id)
                session['appointment_time'] = appointment_time
                session['appointment_date'] = appointment_date
                return redirect(url_for('main.appointment_success', order_id=new_order.id))
            except ValueError as e:
                db.session.rollback()
                return jsonify({'success': False, 'error': str(e)}), 400
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'error': 'Error creating order'}), 500

        if 'selected_services' not in session:
            return redirect(url_for('main.select_services'))

        today = datetime.now().date()
        available_slots = AppointmentSlot.query.filter(
            AppointmentSlot.appointment_date >= today,
            AppointmentSlot.is_available == 1
        ).all()

        return render_template('client/appointments.html', available_slots=available_slots)

    return redirect(url_for('main.index'))

def create_car(client_id, model, vin, license_plate, car_year):
    print(f"Creating car for client_id: {client_id}, model: {model}, vin: {vin}, license_plate: {license_plate}, car_year: {car_year}")
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
    return new_car

def create_order(client_id, car_id):
    print(f"Creating order for client_id: {client_id}, car_id: {car_id}")
    new_order = Order(client_id=client_id, car_id=car_id)
    db.session.add(new_order)
    db.session.commit()

    selected_services = session.get('selected_services', [])
    for service_id in selected_services:
        service = Service.query.get(service_id)
        if service:
            new_order.services.append(service)

    db.session.commit()
    return new_order

def save_order_history(order_id, client_id, car_id):
    print(f"Saving order history for order_id: {order_id}, client_id: {client_id}, car_id: {car_id}")
    new_order_history = OrderHistory(order_id=order_id, client_id=client_id, car_id=car_id)
    db.session.add(new_order_history)
    db.session.commit()

@main.route('/generate_order_pdf/<int:order_id>')
def generate_order_pdf(order_id):
    order = Order.query.get(order_id)
    if not order:
        return "Заказ не найден", 404

    appointment_time = session.get('appointment_time')
    appointment_date = session.get('appointment_date')

    buffer = generate_pdf(order, appointment_time, appointment_date)

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
            name = request.form.get('name')
            role = request.form.get('role')
            email = request.form.get('email')
            password = request.form.get('password')
            hashed_password = generate_password_hash(password)
            new_employee = User(name=name, role=role, email=email, password=hashed_password)
            db.session.add(new_employee)
            db.session.commit()
            return redirect(url_for('main.manage_employees'))
        employees = User.query.filter(User.role.in_(['mechanic', 'manager'])).all()
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
            session['selected_services'] = selected_services
            return redirect(url_for('main.appointments'))
        services = Service.query.all()
        return render_template('client/select_services.html', services=services, form=form)
    return redirect(url_for('main.index'))

@main.route('/order_history')
def order_history():
    if 'role' in session and session['role'] == 'client':
        user = User.query.get(session['user_id'])
        order_history = OrderHistory.query.filter_by(client_id=user.id).all()
        return render_template('client/order_history.html', user=user, order_history=order_history)
    return redirect(url_for('main.index'))

@main.route('/order_details/<int:order_id>')
def order_details(order_id):
    if 'role' in session and session['role'] == 'client':
        user = User.query.get(session['user_id'])
        order = Order.query.get(order_id)
        if not order or order.client_id != user.id:
            return "Заказ не найден", 404
        return render_template('client/order_details.html', user=user, order=order)
    return redirect(url_for('main.index'))