"""
Формы для приложения.

Этот файл содержит определения форм, используемых в приложении, такие как форма для записи клиента
на ремонт и форма для выбора услуг.
"""

from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField, SelectField, DateField, SelectMultipleField
from wtforms.validators import DataRequired
from .models import *

class CarForm(FlaskForm):
    """
    Форма для записи клиента на ремонт.

    Поля:
    - full_name: ФИО клиента.
    - phone: Телефон клиента.
    - car_model: Модель автомобиля (выпадающий список).
    - car_year: Год выпуска автомобиля.
    - vin: VIN номер автомобиля.
    - license_plate: Государственный номер автомобиля.
    - appointment_date: Дата записи.
    - appointment_time: Время записи.
    - submit: Кнопка отправки формы.
    """

    full_name = StringField('ФИО', validators=[DataRequired()])
    phone = StringField('Телефон', validators=[DataRequired()])
    car_model = SelectField('Модель автомобиля', coerce=int, validators=[DataRequired()])
    car_year = IntegerField('Год выпуска', validators=[DataRequired()])
    vin = StringField('VIN номер', validators=[DataRequired()])
    license_plate = StringField('Гос номер', validators=[DataRequired()])
    appointment_date = DateField('Дата записи', format='%Y-%m-%d', validators=[DataRequired()])
    appointment_time = StringField('Время записи', validators=[DataRequired()])
    submit = SubmitField('Записаться')

    def __init__(self, *args, **kwargs):
        """Инициализирует форму и заполняет выпадающий список моделями автомобилей."""
        super(CarForm, self).__init__(*args, **kwargs)
        self.car_model.choices = [(model.id, f"{model.brand} {model.model_name}") for model in CarModel.query.all()]

class SelectServicesForm(FlaskForm):
    """
    Форма для выбора услуг.

    Поля:
    - services: Множественный выбор услуг.
    - submit: Кнопка отправки формы.
    """

    services = SelectMultipleField('Выберите услуги', choices=[])
    submit = SubmitField('Далее')

    def __init__(self, *args, **kwargs):
        """Инициализирует форму и загружает список услуг."""
        super(SelectServicesForm, self).__init__(*args, **kwargs)
        self.services.choices = [(service.id, service.service_name, service.price) for service in Service.query.all()]
