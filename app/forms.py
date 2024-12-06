from flask_wtf import FlaskForm
from wtforms import SubmitField, SelectMultipleField
from .models import Service

class SelectServicesForm(FlaskForm):
    services = SelectMultipleField('Выберите услуги', choices=[])
    submit = SubmitField('Далее')

    def __init__(self, *args, **kwargs):
        super(SelectServicesForm, self).__init__(*args, **kwargs)
        self.services.choices = [(service.id, service.service_name, service.price) for service in Service.query.all()]
