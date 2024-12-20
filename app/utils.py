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

pdfmetrics.registerFont(TTFont('Times-Roman', 'times.ttf'))

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

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setFont("Times-Roman", 14)
    pdf.drawString(1 * inch, 10 * inch, "Автосервис SkodaExpert")
    pdf.setFont("Times-Roman", 12)
    pdf.drawString(1 * inch, 9.5 * inch, f"Номер заказ-наряда: {order.id}")
    pdf.drawString(1 * inch, 9 * inch, f"Имя заказчика: {order.client.name}")
    pdf.drawString(1 * inch, 8.5 * inch, f"Телефон: {order.client.phone}")
    
    # Проверка на None для order.car
    if order.car:
        # Получаем марку и модель автомобиля из таблицы CarModel
        car_model = order.car.car_model
        if car_model:
            pdf.drawString(1 * inch, 8 * inch, f"Марка и модель авто: {car_model.brand} {car_model.model_name}")
        else:
            pdf.drawString(1 * inch, 8 * inch, "Марка и модель авто: Не указано")
        
        pdf.drawString(1 * inch, 7.5 * inch, f"Год выпуска: {order.car.car_year}")
        pdf.drawString(1 * inch, 7 * inch, f"Гос номер: {order.car.license_plate}")
        pdf.drawString(1 * inch, 6.5 * inch, f"VIN код: {order.car.vin}")
    else:
        pdf.drawString(1 * inch, 8 * inch, "Марка и модель авто: Не указано")
        pdf.drawString(1 * inch, 7.5 * inch, "Год выпуска: Не указано")
        pdf.drawString(1 * inch, 7 * inch, "Гос номер: Не указано")
        pdf.drawString(1 * inch, 6.5 * inch, "VIN код: Не указано")

    formatted_date = order.appointment_date.strftime("%d.%m.%Y")
    pdf.drawString(1 * inch, 6 * inch, f"Время записи: {formatted_date} {order.appointment_time}")

    y = 5.5 * inch
    total_price = 0
    pdf.drawString(1 * inch, y, "Выбранные услуги:")
    y -= 0.5 * inch
    for i, service in enumerate(order.services):
        pdf.drawString(1 * inch, y, f"{i + 1}. {service.service_name} - {service.price} руб.")
        total_price += service.price
        y -= 0.5 * inch

    pdf.drawString(1 * inch, y - 0.5 * inch, f"Итого: {total_price} руб.")
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
