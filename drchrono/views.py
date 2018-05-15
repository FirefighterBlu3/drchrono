# Create your views here.
#Django
from django.shortcuts import render, HttpResponse, HttpResponseRedirect, redirect
from django.http import JsonResponse
from django.core import serializers
from django.core.exceptions import SuspiciousOperation
from django.core.urlresolvers import reverse
from django.contrib.auth import logout
from django.contrib import messages
from django.db.models import Q, Value, CharField
from django.db.models.functions import Concat
from django.views.generic import View
from django.views.decorators.csrf import csrf_exempt

from social_django.models import UserSocialAuth

#Project
from .models import Office, Doctor, Patient, Appointment
from .forms import KioskSetupForm, PatientAppointmentForm, DemographicForm
from .utils import fstamp, check_refresh_token, json_get, ISO_639, model_to_dict
from .utils import update_appointment_cache, patch_appointment, seconds_to_text
from .utils import find_avail_timeslots, create_appointment, update_patient_cache

#Python
import datetime
import time
import pytz
import inspect
import json
import re
import traceback

from dateutil.parser import parse as dateparse

from drchrono.settings import SOCIAL_AUTH_DRCHRONO_KEY, SOCIAL_AUTH_DRCHRONO_SECRET

api='https://drchrono.com/api'

# todo: split this into kiosk/views.py and doctor/views.py ...

@csrf_exempt
@fstamp
def webhook(request):
    ''' API callback mechanism
    '''

    for k,v in request.META.items():
        print('whk  {:>40}: {}'.format(k,v))

    secret_token = 'e5bffb72d83c9b52cc1e5ade29cd331657830bef63101f4b74cf005256b847ae'

    if len(request.body) == 0:
        print('webhook request with no body, either a ping, verification, or stranger')

        # unfortunately drchrono API doesn't VERIFY or PING with the secret token so
        # we have to hard code their IP before blindly answering with our secret token
        # !!
        if request.META.get('HTTP_X_FORWARDED_FOR') == '146.20.141.242':
            return JsonResponse({'secret_token':secret_token})

        return JsonResponse({'hi':':-)'})

    if not request.META.get('HTTP_X_DRCHRONO_SIGNATURE') == secret_token:
        print('unrecognized sender, dropping')
        return HttpResponse("i don't know you", status=401)

    event: str = request.META.get('HTTP_X_DRCHRONO_EVENT')
    data = json.loads(request.body)
    print('Received webhook for: {}'.format(event))

    for obj in data:
        print('  {}'.format(obj))
        for k,v in data[obj].items():
            print('    {:>30}: {}'.format(k,v))

    if event.startswith('APPOINTMENT_'):
        update_appointment_cache()
    elif event.startswith('PATIENT_'):
        update_patient_cache()
    elif event.startswith('VACCINE_'):
        update_patient_cache()

    return JsonResponse({'hi':'tyty'})


@fstamp
def home(request):
    '''Doctor; kiosk office choice and interface path
    '''

    data = {
        'offices':Office.objects.all(),
        'form': KioskSetupForm()
    }

    request.session['doctor']: int = Doctor.objects.get(user=UserSocialAuth.objects.get().user).id

    return render(request, 'home.html', data)


@fstamp
def kiosk_path(request):
    ''' This is an interstitial that collects the POST data for the office selection
        and starts the tablet in either Doctor or Kiosk mode

        TODO: put the cache priming behind WAMP for asynchronous updates that
        don't block the startup
    '''

    if not request.method == 'POST':
        raise SuspiciousOperation

    request.session['office']: int = int(request.POST['office'], 10)

    update_patient_cache(request, get_all=True)
    update_appointment_cache(request, get_all=True)
    path: str = request.POST['path']

    if not path in ('drchrono_home', 'kiosk_home'):
        return HttpResponseRedirect(reverse('home'))

    return HttpResponseRedirect(reverse(path))


@fstamp
def drchrono_home(request):
    '''Doctor can pick to view appointment list
    '''

    print(request.POST)
    return render(request, 'drchrono/home.html')


@fstamp
def drchrono_login(request):
    ''' not impl yet
    '''

    return render(request, 'drchrono/login.html')


@fstamp
def drchrono_logout(request):
    ''' also not impl yet
    '''

    logout(request)

    #return HttpResponseRedirect(reverse('index'))
    return render(request, 'drchrono/logout.html')


@fstamp
def drchrono_appointments(request):
    '''
    '''

    now = datetime.datetime.now(pytz.utc) \
                           .astimezone(pytz.timezone('US/Eastern')) \
                           .replace(hour=0, minute=0, second=0, microsecond=0)

    waittimes = [(o.seen_time - o.arrived_time).total_seconds() for o in
                      Appointment.objects.all() if o.scheduled_time and o.seen_time]

    data = [model_to_dict(o) for o in Appointment.objects
                                                 .filter(scheduled_time__date=now)
                                                 .order_by('scheduled_time')]
    for o in data:
        if o['seen_time']:
            o['wait_time_seconds'] = int((o['seen_time'] - o['arrived_time']).total_seconds())
            o['wait_time_display'] = seconds_to_text((o['scheduled_time'] - o['seen_time']).total_seconds())

    return render(request, 'drchrono/appointments.html',
        {'appointments': data,
         'today':        now.astimezone(pytz.timezone('US/Eastern')).strftime('%A, %B %e'),
         'waittimes_sum': int(sum(waittimes)),
         'waittimes_len': len(waittimes),
        })


@fstamp
def kiosk_home(request):
    '''Doctor can pick to view appointment list or patient check in
    '''

    return render(request, 'kiosk/home.html')


@fstamp
@check_refresh_token
def kiosk_check_in(request):
    '''
    '''
    return render(request, 'kiosk/check_in.html')


@fstamp
def kiosk_demographics(request):
    ''' Patient has provided their demographic data after check-in. Verify we have
        an existing record for them.

        0. they are an existing patient and are on today's schedule with 1+ appointment

        *** these conditions are not handled yet ***
        1. if they are a walk-in, they may already have a patient record in the API
        2. they may be a wholly new patient and no record exists for them
        3. they may have made a typo
    '''

    if not request.method == 'POST':
        raise SuspiciousOperation

    print(request.POST)
    first_name: str = request.POST.get('first_name')
    last_name: str = request.POST.get('last_name')
    appt: str = request.POST.get('appointment-selection')
    dob: str  = request.POST['date_of_birth']
    dob  = dateparse(dob).strftime('%F')

    query = Q(first_name__exact=first_name)
    query.add(Q(last_name__exact=last_name), Q.AND)
    query.add(Q(date_of_birth=dob), Q.AND)

    try:
        patient = Patient.objects.get(query)

    except Patient.MultipleObjectsReturned:
        print('*** more than one copy of this patient?')
        ''' here we ought to collect all the apparent duplicate
            patients and send an email off to someone that can
            resolve the issue. automatic bug issue filer? would
            be nice
        '''
        pts = Patient.objects.filter(query).all()

        print('Duplicates: {}'.format(pts.count()))
        for p in pts:
            print('Dupe: #{}'.format(p.id))
            for k,v in p:
                print('  {:>30}: {}'.format(k,v))
            print()

        messages.error(request, 'Error: Multiple instances of you in database, please see receptionist to check in')
        return HttpResponseRedirect(reverse('kiosk_check_in'))

    except Patient.DoesNotExist:
        print('Creating a new patient: {}'.format(request.POST))
        f, l = name.split(' ',1)
        patient = Patient(
                first_name=f,
                last_name=l,
                date_of_birth=dob
            )


    #patch_patient(request, a.id, {'status':a.status})

    form = DemographicForm(instance=patient)
    return render(request, 'kiosk/checked_in.html', {'form':form})


@fstamp
def kiosk_checked_in(request):
    '''
    '''

    if not request.method == 'POST':
        raise SuspiciousOperation

    patient = Patient.objects.get(id=request.session['drchrono_patient_checked_in'])

    print(request.POST)
    form = DemographicForm(request.POST)
    if form.is_valid():
        form.save()

    doctor: int = request.session['doctor']
    return render(request, 'kiosk/checked_in.html', {'doctor': Doctor.objects.get(id=doctor)})


@fstamp
def ajax_see_patient(request):
    '''
    '''

    if not request.method == 'POST':
        raise SuspiciousOperation

    id          = request.POST.get('id')
    status: str = request.POST.get('status')

    appt   = Appointment.objects.get(id=id)

    if status == "true":
        status = "In Session"
    else:
        status = appt.prior_status

    if status == 'In Session':
        appt.seen_time = datetime.datetime.now(pytz.utc)
    else:
        appt.seen_time = None

    appt.prior_status = appt.status
    appt.status = status
    appt.save()

    patch_appointment(request, id, {'status':status})

    return JsonResponse({'hi':'tyty', 'status':status})


@fstamp
def ajax_checkin_autocomplete(request):
    '''
    '''

    now = datetime.datetime.now(pytz.utc) \
                           .astimezone(pytz.timezone('US/Eastern')) \
                           .replace(hour=0, minute=0, second=0, microsecond=0)

    callback = request.GET.get('callback')
    term     = request.GET.get('term').lower()

    qs = Patient.objects.annotate(
                full_name=Concat(
                    'first_name',
                    Value(' '),
                    'last_name',
                    output_field=CharField()
                )
            ).filter(Q(full_name__icontains=term) |
                     Q(first_name__icontains=term) |
                     Q(last_name__icontains=term)
            ).order_by('first_name')

    results = sorted(set([str(o) for o in qs]))

    response_prose='{}({{result:{}}})'.format(callback, results)
    #print(response_prose)
    return HttpResponse(response_prose, "text/javascript")


@fstamp
def ajax_checkin_appointments(request):
    ''' Intent is to provide a list of times if there is more than one appointment
        for this patient
    '''

    if not request.method == 'GET':
        raise SuspiciousOperation

    now = datetime.datetime.now(pytz.utc) \
                           .astimezone(pytz.timezone('US/Eastern')) \
                           .replace(hour=0, minute=0, second=0, microsecond=0)

    callback = request.GET.get('callback')
    name     = request.GET.get('name').lower()
    try:
        dob = dateparse(request.GET['dob']).strftime('%F')
    except:
        # make it an impossible date (if this code is still running in 2038, ... THAT is impossible)
        dob = '2038-01-01'

    queryset=Patient.objects.annotate(search_name=Concat('first_name',
                                                              Value(' '),
                                                             'last_name'))
    try:
        patient = queryset.get(search_name__iexact=name, date_of_birth=dob)
    except Patient.DoesNotExist:
        # probably a walk-in
        results = [[-1,"I want a walk-in appointment"]]

        response_prose='{}({{result:{}}})'.format(callback, list(results))
        return HttpResponse(response_prose, "text/javascript")

    query = Q(scheduled_time__date=now)
    query.add(Q(patient__id=patient.id), Q.AND)

    try:
        data = [o for o in Appointment.objects
                            .filter(query)
                            .order_by('scheduled_time', 'patient__first_name')]

    except Appointment.DoesNotExist:
        # probably a walk-in
        results = [[-1,"I want a walk-in appointment"]]

        response_prose='{}({{result:{}}})'.format(callback, list(results))
        return HttpResponse(response_prose, "text/javascript")

    # build as a list of tuples first...
    results = [(o.id,o.scheduled_time
                .astimezone(pytz.timezone('US/Eastern'))
                .strftime('%l:%M%P')
                .strip()) for o in data]

    # so they are guaranteed unique...
    results = list(set(results))

    # and add the walk-in...
    results += [(-1, "I want a walk-in appointment")]

    # then make it a list of lists because javascript has no notion of tuples and
    # we're building the json by hand
    results = [[a,b] for a,b in results]

    response_prose='{}({{result:{}}})'.format(callback, list(results))
    return HttpResponse(response_prose, "text/javascript")


@fstamp
def ajax_walkin_find_avail_time(request):
    ''' Try to find the next available time slot for a walk-in appointment
    '''

    if not request.method == 'GET':
        raise SuspiciousOperation

    # iterate all of today's appointments, collect their start time+duration
    # build a map of open slots that are at least NN minutes (duration) available
    # the list of available slots should consist tuple of Time, Duration
    now = datetime.datetime.now(pytz.utc) \
                           .astimezone(pytz.timezone('US/Eastern')) \
                           .replace(hour=0, minute=0, second=0, microsecond=0)

    callback = request.GET.get('callback')

    query = Q(scheduled_time__date=now)
    schedule = [(o.scheduled_time,o.duration) for o in Appointment
                                                      .objects
                                                      .filter(query)
                                                      .order_by('scheduled_time')]
    slots = find_avail_timeslots(schedule)

    # localize
    slots = [(tm.astimezone(pytz.timezone('US/Eastern')),duration) for tm,duration in slots]

    results = ['{} for {} minutes'.format(t.strftime('%l:%M%P'), d).strip() for t,d in slots]

    response_prose='{}({{result:{}}})'.format(callback, results)
    return HttpResponse(response_prose, "text/javascript")


@fstamp
def ajax_checkin_appointment_create(request):
    ''' Patient has requested a walk-in appointment
    '''

    if not request.method == 'POST':
        raise SuspiciousOperation

    print(request.POST)
    name = request.POST.get('name').lower()
    appt = request.POST.get('appointment_time')
    dob  = request.POST.get('dob')

    # verify the patient exists in our DB
    try:
        dob = dateparse(dob).strftime('%F')
        appt_time = pytz.timezone('US/Eastern').localize( dateparse(appt.split()[0]) )
        print('appt time: {}'.format(appt_time))

    except:
        print('newp')
        raise SuspiciousOperation

    queryset=Patient.objects.annotate(search_name=Concat('first_name',
                                                          Value(' '),
                                                         'last_name'))
    try:
        patient = queryset.get(search_name__iexact=name,
                                date_of_birth=dob)

    except Patient.DoesNotExist:
        return JsonResponse({'status':'unknown patient'})

    # create appt
    create_appointment(request, patient, scheduled_time=appt_time, is_walk_in=True, duration=30)

    # return appt id

    return JsonResponse({'status':'tyty'})


@fstamp
def ajax_checkin_complete(request):
    ''' Patient correctly identified self and selected their
        appointment time
    '''

    if not request.method == 'POST':
        raise SuspiciousOperation

    print(request.POST)
    name = request.POST.get('name').lower()
    appt = int(request.POST.get('appointment_id'), 10)
    dob  = request.POST.get('dob')

    form = PatientAppointmentForm({
        'id':appt,
        'name':name,
        'date_of_birth':dob
        })

    if not form.is_valid():
        print('form data invalid: {}'.format(form.errors))
        raise SuspiciousOperation(form.errors)


    if appt == 'Walk-in':
        print('creating a new appointment')
        # check the schedule, find the next available slot

    else:
        id = form.cleaned_data.get('id')
        print('appointment id is: {}'.format(id))
        a = Appointment.objects.get(id=id)
        a.status = 'Checked In'
        a.arrived_time = datetime.datetime.now(pytz.utc)
        a.save()

        request.session['drchrono_patient_checked_in']=a.patient.id

        for k,v in a:
            print('  {:>30}: {!r}'.format(k,v))

        patch_appointment(request, a.id, {'status':a.status})

    return JsonResponse({'hi':'tyty'})


@fstamp
def ajax_checkin_demographics(request):
    '''
    '''
    if not request.method == 'GET':
        raise SuspiciousOperation

    callback = request.GET.get('callback')
    name     = request.GET.get('name').lower()

    try:
        dob = dateparse(request.GET['dob']).strftime('%F')
    except:
        # make it an impossible date (if this code is still running in 2038, ... THAT is impossible)
        dob = '2038-01-01'

    queryset=Patient.objects.annotate(search_name=Concat('first_name',
                                                          Value(' '),
                                                         'last_name'))
    try:
        patient = queryset.get(search_name__iexact=name,
                                date_of_birth=dob)
    except Patient.DoesNotExist:
        # probably a walk-in
        results = ["Patient not Found!"]

        response_prose='{}({{result:{}}})'.format(callback, list(results))
        return HttpResponse(response_prose, "text/javascript")

    r1 = {k:v for k,v in patient if not k in ('id',)}
    results = {}
    for k,v in r1.items():
        if k == 'date_of_birth':
            v = v.strftime('%F')
        elif v == 'blank':
            v = ''
        results[k]=v

    response_prose='{}({{result:{}}})'.format(callback, results)
    return HttpResponse(response_prose, "text/javascript")
