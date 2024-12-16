"""
Формы для приложения.

Этот файл содержит определения форм, используемых в приложении, таких как форма для записи клиента
на ремонт и форма для выбора услуг.
"""

from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField, SelectMultipleField, DateField, SelectField
from wtforms.validators import DataRequired
from .models import Service, CarModel
import logging

logging.basicConfig(level=logging.DEBUG)

class CarForm(FlaskForm):
    """Форма для записи клиента на ремонт."""
    full_name = StringField('ФИО', validators=[DataRequired()])
    phone = StringField('Телефон', validators=[DataRequired()])
    model = SelectField('Модель автомобиля', coerce=int, validators=[DataRequired()])
    car_year = IntegerField('Год выпуска', validators=[DataRequired()])
    vin = StringField('VIN номер', validators=[DataRequired()])
    license_plate = StringField('Гос номер', validators=[DataRequired()])
    appointment_date = DateField('Дата записи', format='%Y-%m-%d', validators=[DataRequired()])
    appointment_time = StringField('Время записи', validators=[DataRequired()])
    submit = SubmitField('Записаться')

    def __init__(self, *args, **kwargs):
        super(CarForm, self).__init__(*args, **kwargs)
        self.model.choices = [(model.id, f"{model.brand} {model.model_name}") for model in CarModel.query.all()]

    def validate(self):
        """Проверяет валидность формы."""
        if not super(CarForm, self).validate():
            logging.debug(f"Form validation failed: {self.errors}")
            return False
        return True

class SelectServicesForm(FlaskForm):
    """Форма для выбора услуг."""
    services = SelectMultipleField('Выберите услуги', choices=[])
    submit = SubmitField('Далее')

    def __init__(self, *args, **kwargs):
        """Инициализирует форму и загружает список услуг."""
        super(SelectServicesForm, self).__init__(*args, **kwargs)
        self.services.choices = [(service.id, service.service_name, service.price) for service in Service.query.all()]
