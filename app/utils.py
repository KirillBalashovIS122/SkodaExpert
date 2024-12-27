from flask import session, make_response
from .models import Employee, Client, Order, Service, Task, Report, OrderService
from . import db
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
import os
import logging

logging.basicConfig(level=logging.DEBUG)

STATUS_TRANSLATIONS = {
    'pending': 'В ожидании',
    'in_progress': 'В процессе',
    'completed': 'Завершено'
}

def translate_status(status):
    return STATUS_TRANSLATIONS.get(status, status)

def get_current_user():
    user_id = session.get('user_id')
    role = session.get('role')
    if role == 'client':
        return Client.query.get(user_id)
    elif role in ['mechanic', 'manager']:
        return Employee.query.get(user_id)
    return None

def generate_pdf(order):
    if not order.appointment_date or not order.appointment_time:
        raise ValueError("Время и дата записи не могут быть None")

    pdfmetrics.registerFont(TTFont('Arial', 'Arial.ttf'))

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setFont("Arial", 14)

    logo_path = os.path.join(os.path.dirname(__file__), 'static', 'logo.png')
    if os.path.exists(logo_path):
        pdf.drawImage(logo_path, 1 * inch, 10.5 * inch, width=1.5 * inch, height=0.75 * inch)

    pdf.drawString(2.5 * inch, 10.75 * inch, "Автосервис SkodaExpert")
    pdf.setFont("Arial", 12)

    pdf.drawString(1 * inch, 9.5 * inch, f"Номер заказ-наряда: {order.id}")
    pdf.drawString(1 * inch, 9 * inch, f"Имя заказчика: {order.client.name}")
    pdf.drawString(1 * inch, 8.5 * inch, f"Телефон: {order.client.phone}")
    pdf.drawString(1 * inch, 8 * inch, f"Марка и модель авто: {order.car_brand} {order.car_model}")
    pdf.drawString(1 * inch, 7.5 * inch, f"Год выпуска: {order.car.car_year}")
    pdf.drawString(1 * inch, 7 * inch, f"Гос номер: {order.car.license_plate}")
    pdf.drawString(1 * inch, 6.5 * inch, f"VIN код: {order.car.vin}")
    formatted_date = order.appointment_date.strftime("%d.%m.%Y")
    pdf.drawString(1 * inch, 6 * inch, f"Время записи: {formatted_date} {order.appointment_time}")

    pdf.drawString(1 * inch, 5.5 * inch, "Выбранные услуги:")
    y_position = 5 * inch
    total_price = 0

    for service in order.services:
        pdf.drawString(1.5 * inch, y_position, f"- {service.service_name}: {service.price} руб.")
        total_price += service.price
        y_position -= 0.25 * inch

    pdf.drawString(1 * inch, y_position - 0.5 * inch, f"Итоговая стоимость: {total_price} руб.")

    pdf.save()
    buffer.seek(0)
    return buffer

def calculate_statistics():
    total_orders = Order.query.count()
    total_revenue = sum(sum(service.price for service in order.services) for order in Order.query.all())

    service_statistics = db.session.query(
        Service.service_name,
        db.func.count(OrderService.order_id).label('count'),
        db.func.sum(Service.price).label('total_price')
    ).join(OrderService, Service.id == OrderService.service_id).group_by(Service.service_name).all()

    employee_statistics = db.session.query(
        Employee.name,
        db.func.count(Task.id).label('task_count'),
        db.func.count(Report.id).label('report_count')
    ).outerjoin(Task).outerjoin(Report).group_by(Employee.name).all()

    return {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'service_statistics': service_statistics,
        'employee_statistics': employee_statistics
    }
