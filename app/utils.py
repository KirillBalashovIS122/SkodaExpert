from flask import session
from .models import User, Order, Service, Task, Report
from . import db
from datetime import datetime

def get_current_user():
    user_id = session.get('user_id')
    role = session.get('role')
    if role == 'client':
        return User.query.get(user_id)
    elif role in ['mechanic', 'manager']:
        return User.query.get(user_id)
    return None

def generate_pdf(order, appointment_time, appointment_date):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
    from io import BytesIO
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    pdfmetrics.registerFont(TTFont('Times-Roman', 'times.ttf'))

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setFont("Times-Roman", 14)
    pdf.drawString(1 * inch, 10 * inch, "Автосервис SkodaExpert")
    pdf.setFont("Times-Roman", 12)
    pdf.drawString(1 * inch, 9.5 * inch, f"Номер заказ-наряда: {order.id}")
    pdf.drawString(1 * inch, 9 * inch, f"Имя заказчика: {order.user.name}")
    pdf.drawString(1 * inch, 8.5 * inch, f"Телефон: {order.user.phone}")
    pdf.drawString(1 * inch, 8 * inch, f"Марка и модель авто: {order.car.model}")
    pdf.drawString(1 * inch, 7.5 * inch, f"Год выпуска: {order.car.car_year}")
    pdf.drawString(1 * inch, 7 * inch, f"Гос номер: {order.car.license_plate}")
    pdf.drawString(1 * inch, 6.5 * inch, f"VIN код: {order.car.vin}")

    formatted_date = datetime.strptime(appointment_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    pdf.drawString(1 * inch, 6 * inch, f"Время записи: {formatted_date} {appointment_time}")

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
        db.func.count(Order.id).label('count'),
        db.func.sum(Service.price).label('total_price')
    ).join(Order).group_by(Service.service_name).all()

    employee_statistics = db.session.query(
        User.name,
        db.func.count(Task.id).label('task_count'),
        db.func.count(Report.id).label('report_count')
    ).outerjoin(Task).outerjoin(Report).group_by(User.name).all()

    return {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'service_statistics': service_statistics,
        'employee_statistics': employee_statistics
    }
