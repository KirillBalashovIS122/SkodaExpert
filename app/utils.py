from flask import session, make_response, render_template
from .models import *
from . import db
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from sqlalchemy import func, text
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
    """
    Переводит статус заказа на русский язык.

    :param status: Статус заказа (str).
    :return: Переведенный статус (str).
    """
    return STATUS_TRANSLATIONS.get(status, status)

def get_current_user():
    """
    Возвращает текущего пользователя на основе данных сессии.

    :return: Объект пользователя (Client или Employee) или None, если пользователь не найден.
    """
    user_id = session.get('user_id')
    role = session.get('role')
    if role == 'client':
        return Client.query.get(user_id)
    elif role in ['mechanic', 'manager']:
        return Employee.query.get(user_id)
    return None

def generate_pdf(order):
    """
    Генерирует PDF-документ для заказа.

    :param order: Объект заказа.
    :return: BytesIO объект с содержимым PDF.
    :raises ValueError: Если время или дата записи не указаны.
    """
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

def generate_manager_report(start_date=None, end_date=None):
    """
    Генерирует отчет для менеджера, включая:
    - Общее количество заказов
    - Статистику по моделям машин
    - Общий доход
    - Финансовые показатели по услугам

    :param start_date: Начальная дата периода (datetime.date, str или None).
    :param end_date: Конечная дата периода (datetime.date, str или None).
    :return: Словарь с данными отчета.
    """
    try:
        logging.debug("Starting generate_manager_report function")
        
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        params = {
            "start_date": start_date.strftime('%Y-%m-%d') if start_date else "1900-01-01",
            "end_date": end_date.strftime('%Y-%m-%d') if end_date else "9999-12-31",
        }
        
        total_orders_query = """
            SELECT 
                COUNT(o.id) AS total_orders
            FROM 
                orders o
            WHERE 
                o.created_at >= COALESCE(:start_date, '1900-01-01')
                AND o.created_at <= COALESCE(:end_date, '9999-12-31')
        """
        logging.debug(f"Executing total orders query: {total_orders_query} with params: {params}")
        total_orders = db.session.execute(text(total_orders_query), params).scalar()
        logging.debug(f"Total orders: {total_orders}")

        orders_by_model_query = """
            SELECT 
                cm.brand,
                cm.model_name,
                COUNT(o.id) AS order_count
            FROM 
                car_models cm
            JOIN 
                cars c ON cm.id = c.car_model_id
            JOIN 
                orders o ON c.id = o.car_id
            WHERE 
                o.created_at >= COALESCE(:start_date, '1900-01-01')
                AND o.created_at <= COALESCE(:end_date, '9999-12-31')
            GROUP BY 
                cm.brand, cm.model_name
        """
        logging.debug(f"Executing orders by model query: {orders_by_model_query} with params: {params}")
        orders_by_model_result = db.session.execute(text(orders_by_model_query), params)
        orders_by_model = [
            {"brand": row[0], "model_name": row[1], "order_count": row[2]}
            for row in orders_by_model_result
        ]
        logging.debug(f"Orders by model: {orders_by_model}")

        revenue_query = """
            SELECT 
                CAST(COALESCE(SUM(s.price), 0) AS NUMERIC(10, 2)) AS total_revenue
            FROM 
                services s
            JOIN 
                order_services os ON s.id = os.service_id
            JOIN 
                orders o ON os.order_id = o.id
            WHERE 
                o.created_at >= COALESCE(:start_date, '1900-01-01')
                AND o.created_at <= COALESCE(:end_date, '9999-12-31')
        """
        logging.debug(f"Executing revenue query: {revenue_query} with params: {params}")
        total_revenue = db.session.execute(text(revenue_query), params).scalar()
        logging.debug(f"Total revenue: {total_revenue}")

        revenue_by_service_query = """
            SELECT 
                s.service_name,
                CAST(COALESCE(SUM(s.price), 0) AS NUMERIC(10, 2)) AS revenue
            FROM 
                services s
            JOIN 
                order_services os ON s.id = os.service_id
            JOIN 
                orders o ON os.order_id = o.id
            WHERE 
                o.created_at >= COALESCE(:start_date, '1900-01-01')
                AND o.created_at <= COALESCE(:end_date, '9999-12-31')
            GROUP BY 
                s.service_name
        """
        logging.debug(f"Executing revenue by service query: {revenue_by_service_query} with params: {params}")
        revenue_by_service_result = db.session.execute(text(revenue_by_service_query), params)
        revenue_by_service = [
            {"service_name": row[0], "revenue": float(row[1])}
            for row in revenue_by_service_result
        ]
        logging.debug(f"Revenue by service: {revenue_by_service}")

        return {
            "total_orders": total_orders,
            "orders_by_model": orders_by_model,
            "total_revenue": float(total_revenue) if total_revenue else 0.0,
            "revenue_by_service": revenue_by_service,
        }
    except Exception as e:
        logging.error(f"Error in generate_manager_report: {e}", exc_info=True)
        raise
