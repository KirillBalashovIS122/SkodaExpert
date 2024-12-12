from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey, Date, Time
from sqlalchemy.orm import relationship
from . import db

class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(255))  # Объединенная строка из last_name, first_name и middle_name
    email = db.Column(String(255), unique=True)
    phone = db.Column(String(20))
    password = db.Column("PASSWORD", String(255))
    role = db.Column(String(50))
    created_at = db.Column(DateTime, default=datetime.utcnow)

class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(100), nullable=False)
    email = db.Column(String(100), nullable=False, unique=True)
    phone = db.Column(String(15), nullable=False, unique=True)
    password = db.Column(String(200), nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow)

class Car(db.Model):
    __tablename__ = 'cars'
    id = db.Column(Integer, primary_key=True)
    client_id = db.Column(Integer, ForeignKey('clients.id'), nullable=False)
    model = db.Column(String(100), nullable=False)
    car_year = db.Column(Integer, nullable=False)
    vin = db.Column(String(17), nullable=False, unique=True)
    license_plate = db.Column(String(12), nullable=False, unique=True)
    created_at = db.Column(DateTime, default=datetime.utcnow)

class Service(db.Model):
    __tablename__ = 'services'
    id = db.Column(Integer, primary_key=True)
    service_name = db.Column(String(100), nullable=False)
    description = db.Column(Text)
    price = db.Column(Float, nullable=False)
    duration = db.Column(Integer, nullable=False)

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(Integer, primary_key=True)
    client_id = db.Column(Integer, ForeignKey('clients.id'), nullable=False)
    car_id = db.Column(Integer, ForeignKey('cars.id'), nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    appointment_date = db.Column(Date, nullable=False)
    appointment_time = db.Column(Time, nullable=False)
    end_time = db.Column(Time, nullable=False)  # Добавляем поле end_time
    car = db.relationship('Car', backref='orders')
    client = db.relationship('Client', backref='orders')
    services = db.relationship('Service', secondary='order_services', backref='orders')

class OrderService(db.Model):
    __tablename__ = 'order_services'
    order_id = db.Column(Integer, ForeignKey('orders.id'), primary_key=True)
    service_id = db.Column(Integer, ForeignKey('services.id'), primary_key=True)

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(Integer, primary_key=True)
    employee_id = db.Column(Integer, ForeignKey('employees.id'), nullable=False)
    order_id = db.Column(Integer, ForeignKey('orders.id'), nullable=False)
    status = db.Column(String(50), default='pending')  # Добавляем поле статуса
    created_at = db.Column(DateTime, default=datetime.utcnow)

    employee = db.relationship('Employee', backref='tasks')
    order = db.relationship('Order', backref='tasks')

class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(Integer, primary_key=True)
    task_id = db.Column(Integer, ForeignKey('tasks.id'), nullable=False)
    description = db.Column(Text, nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow)

class OrderHistory(db.Model):
    __tablename__ = 'order_history'
    id = db.Column(Integer, primary_key=True)
    order_id = db.Column(Integer, ForeignKey('orders.id'), nullable=False)
    client_id = db.Column(Integer, ForeignKey('clients.id'), nullable=False)
    car_id = db.Column(Integer, ForeignKey('cars.id'), nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow)
