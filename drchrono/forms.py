# forms go here
from django import forms
from django.db.models.functions import Concat
from django.db.models import Q, Value, CharField

from .models import Patient, Office, Appointment

import re
import datetime

class KioskSetupForm(forms.Form):
    office = forms.ModelChoiceField(queryset=Office.objects.all(),
                                    widget=forms.RadioSelect,
                                    empty_label=None,
                                    label='Office selection for this Kiosk')

    # class Meta:
    #     model = Office
    #     fields = ('name',)
    #     labels = {'name':'Office selection for this Kiosk'}
    #     widgets = {
    #             'name': forms.RadioSelect,
    #         }
    #     #choice = forms.modelChoiceField(queryset=)

    # def __init__(self, *args, **kwargs):
    #     super(KioskSetupForm, self).__init__(*args, **kwargs)
    #     #self.fields['name'].choices = Office.objects.all()



class PatientAppointmentForm(forms.Form):
    id = forms.IntegerField(required=True)
    name = forms.CharField(required=True, max_length=64)
    date_of_birth = forms.DateField(required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


    def clean_id(self):
        obj = self.cleaned_data.get('id')
        if not obj:
            self.add_error(field='id', error='invalid Appointment ID')
        if not isinstance(obj, int):
            self.add_error(field='id', error='invalid Appointment ID')

        # special id for a walk-in appointment that is pending
        if obj == -1:
            return obj

        try:
            q = Appointment.objects.get(id=obj)
        except:
            self.add_error(field='id', error='invalid Appointment ID')

        return obj


    def clean_name(self):
        obj = self.cleaned_data.get('name')
        if not obj:
            self.add_error(field='name', error='invalid Name')
        if not isinstance(obj, str):
            self.add_error(field='name', error='invalid Name')

        qs = Patient.objects.annotate(
                full_name=Concat(
                    'first_name',
                    Value(' '),
                    'last_name',
                    output_field=CharField()
                )
            ).filter(Q(full_name__icontains=obj)
            ).order_by('first_name')

        r = qs.get()

        self.patient_dob = r.date_of_birth

        return obj


    def clean_date_of_birth(self):
        obj = self.cleaned_data.get('date_of_birth')
        if not obj:
            self.add_error(field='date_of_birth', error='invalid Date of Birth')
        if not isinstance(obj, datetime.date):
            self.add_error(field='date_of_birth', error='invalid Date of Birth')
        if not self.patient_dob == obj:
            self.add_error(field='date_of_birth', error='invalid Date of Birth')

        return obj



class DemographicForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['first_name', 'middle_name', 'last_name', 'gender',

                  'address', 'city', 'state', 'zip_code',

                  'date_of_birth', 'social_security_number',
                  'ethnicity', 'race', 'preferred_language',

                  'cell_phone', 'email',

                  'emergency_contact_relation', 'emergency_contact_name', 'emergency_contact_phone',
                  ]

    def __init__(self, *args, **kwargs):
        super(DemographicForm, self).__init__(*args, **kwargs)

        for key in self.fields:
            self.fields[key].required = False

        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            field.widget.attrs['autocomplete'] = 'disabled'
