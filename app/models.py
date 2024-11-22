from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey
from . import db

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(255))
    email = db.Column(String(255))
    phone = db.Column(String(20))
    password = db.Column("PASSWORD", String(255))
    role = db.Column(String(50))
    created_at = db.Column(DateTime, default=datetime.utcnow)

class Client(db.Model):
    __tablename__ = 'CLIENTS'
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(100), nullable=False)
    email = db.Column(String(100), nullable=False, unique=True)
    phone = db.Column(String(15), nullable=False, unique=True)
    password = db.Column(String(200), nullable=False)
    created_at = db.Column(DateTime, default=db.func.current_timestamp())

class Car(db.Model):
    __tablename__ = 'cars'
    id = db.Column(Integer, primary_key=True)
    client_id = db.Column(Integer, db.ForeignKey('CLIENTS.id'), nullable=False)
    model = db.Column(String(100), nullable=False)
    car_year = db.Column(Integer, nullable=False)
    vin = db.Column(String(17), nullable=False)
    license_plate = db.Column(String(12), nullable=False)
    created_at = db.Column(DateTime, default=db.func.current_timestamp())

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
    client_id = db.Column(Integer, db.ForeignKey('CLIENTS.ID'), nullable=False)
    car_id = db.Column(Integer, db.ForeignKey('cars.id'), nullable=False)
    created_at = db.Column(DateTime, default=db.func.current_timestamp())

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(Integer, primary_key=True)
    employee_id = db.Column(Integer, db.ForeignKey('users.id'), nullable=False)
    order_id = db.Column(Integer, db.ForeignKey('orders.id'), nullable=False)
    status = db.Column(String(50), default='pending')
    created_at = db.Column(DateTime, default=db.func.current_timestamp())

class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(Integer, primary_key=True)
    task_id = db.Column(Integer, db.ForeignKey('tasks.id'), nullable=False)
    description = db.Column(Text, nullable=False)
    created_at = db.Column(DateTime, default=db.func.current_timestamp())

class AppointmentSlot(db.Model):
    __tablename__ = 'appointment_slots'
    id = db.Column(Integer, primary_key=True)
    appointment_date = db.Column(DateTime, nullable=False)
    start_time = db.Column(DateTime, nullable=False)
    end_time = db.Column(DateTime, nullable=False)
    is_available = db.Column(Boolean, default=True)
