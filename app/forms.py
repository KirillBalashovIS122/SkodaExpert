from flask_wtf import FlaskForm
from wtforms import SubmitField, SelectMultipleField
from .models import Service
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired

class SelectServicesForm(FlaskForm):
    services = SelectMultipleField('Выберите услуги', choices=[])
    submit = SubmitField('Далее')

    def __init__(self, *args, **kwargs):
        super(SelectServicesForm, self).__init__(*args, **kwargs)
        self.services.choices = [(service.id, service.service_name, service.price) for service in Service.query.all()]

class CarForm(FlaskForm):
    model = StringField('Модель автомобиля', validators=[DataRequired()])
    car_year = IntegerField('Год выпуска', validators=[DataRequired()])
    vin = StringField('VIN номер', validators=[DataRequired()])
    license_plate = StringField('Гос номер', validators=[DataRequired()])
    submit = SubmitField('Записаться')
