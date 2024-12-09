from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField, SelectMultipleField 
from wtforms import DateField
from wtforms.validators import DataRequired
from .models import Service
from wtforms import DateTimeField

class SelectServicesForm(FlaskForm):
    services = SelectMultipleField('Выберите услуги', choices=[])
    submit = SubmitField('Далее')

    def __init__(self, *args, **kwargs):
        super(SelectServicesForm, self).__init__(*args, **kwargs)
        self.services.choices = [(service.id, service.service_name, service.price) for service in Service.query.all()]

class CarForm(FlaskForm):
    full_name = StringField('ФИО', validators=[DataRequired()])
    phone = StringField('Телефон', validators=[DataRequired()])
    model = StringField('Модель автомобиля', validators=[DataRequired()])
    car_year = IntegerField('Год выпуска', validators=[DataRequired()])
    vin = StringField('VIN номер', validators=[DataRequired()])
    license_plate = StringField('Гос номер', validators=[DataRequired()])
    appointment_date = DateTimeField('Дата записи', format='%Y-%m-%d %H:%M', validators=[DataRequired()])
    submit = SubmitField('Записаться')
