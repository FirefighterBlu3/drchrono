from django.contrib import admin
from .models import Office, Doctor, Patient, Appointment

admin.site.register(Office)
admin.site.register(Doctor)
admin.site.register(Patient)
admin.site.register(Appointment)
