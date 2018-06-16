# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


def validate_gender(value):
    v = value.lower()
    if v not in ('m', 'male', 'f', 'female', 'h', 'hermaphrodite'):
        raise ValidationError('%(value)s is not a valid gender',
                              params={'value': value})


def validate_appt_status(value):
    if value not in ("", "Arrived", "Checked In", "In Room", "Cancelled",
                     "Complete", "Confirmed", "In Session", "No Show",
                     "Not Confirmed", "Rescheduled"):
        raise ValidationError('%(value)s is not a valid status',
                              params={'value': value})


class Office(models.Model):
    id           = models.IntegerField(primary_key=True)
    name         = models.CharField(max_length=64, null=True)
    address      = models.CharField(max_length=64, null=True)
    phone_number = models.CharField(max_length=12, null=True)

    def __str__(self):
        return self.name


class Doctor(models.Model):
    id           = models.IntegerField(primary_key=True)
    first_name   = models.CharField(max_length=30)
    last_name    = models.CharField(max_length=30)
    user         = models.OneToOneField(User, on_delete=models.CASCADE)
    office       = models.IntegerField(default=3456)

    access_token      = models.CharField(max_length=200)
    refresh_token     = models.CharField(max_length=200)
    expires_timestamp = models.CharField(max_length=200)

    def __str__(self):
        first_name = str(self.first_name)[2:-3]
        last_name = str(self.last_name)[2:-3]
        return '{} {}'.format(first_name, last_name)

    def __iter__(self):
        for field in self._meta.fields:
            value = getattr(self, field.name, None)
            yield (field.name, value)


# todo: some of these fields should not be required

class Patient(models.Model):
    id                         = models.IntegerField(primary_key=True)
    first_name                 = models.CharField(max_length=30)
    middle_name                = models.CharField(max_length=30, null=True)
    last_name                  = models.CharField(max_length=30)
    date_of_birth              = models.DateField(null=True)
    gender                     = models.CharField(max_length=15, null=True,
                                                  validators=[validate_gender])
    address                    = models.CharField(max_length=50, null=True)
    city                       = models.CharField(max_length=20, null=True)
    state                      = models.CharField(max_length=2, null=True)
    zip_code                   = models.CharField(max_length=10, null=True)
    cell_phone                 = models.CharField(max_length=12, null=True)
    email                      = models.CharField(max_length=40, null=True)
    emergency_contact_name     = models.CharField(max_length=40, null=True)
    emergency_contact_phone    = models.CharField(max_length=12, null=True)
    emergency_contact_relation = models.CharField(max_length=20, null=True)
    ethnicity                  = models.CharField(max_length=20, null=True)
    preferred_language         = models.CharField(max_length=20, null=True)
    race                       = models.CharField(max_length=20, null=True)
    social_security_number     = models.CharField(max_length=11, null=True)
    patient_photo              = models.URLField(null=True)

    def __str__(self):
        mid = ' '+self.middle_name[0] if self.middle_name else ''
        return ' '.join([self.first_name, mid, self.last_name])

    def __iter__(self):
        for field in self._meta.fields:
            value = getattr(self, field.name, None)
            yield (field.name, value)


class Appointment(models.Model):
    id                      = models.IntegerField(primary_key=True)
    scheduled_time          = models.DateTimeField()
    patient                 = models.ForeignKey(Patient,
                                                related_name='id+',
                                                on_delete=models.CASCADE)
    duration                = models.IntegerField(default=30)
    reason                  = models.CharField(max_length=64, default="")
    status                  = models.CharField(max_length=30, default="",
                                               null=True,
                                               validators=[validate_appt_status])
    exam_room               = models.IntegerField(default=1)


    # local fields, not synched with API
    arrived_time            = models.DateTimeField(null=True)
    seen_time               = models.DateTimeField(null=True)
    prior_status            = models.CharField(max_length=30, default="",
                                               null=True,
                                               validators=[validate_appt_status])
    preferred_language_full = models.CharField(max_length=30, default="")

    def __str__(self):
        return str(self.id)

    def __iter__(self):
        for field in self._meta.fields:
            value = getattr(self, field.name, None)
            yield (field.name, value)
