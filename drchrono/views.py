# todo: split this into kiosk/views.py and doctor/views.py ...

# Python
import requests
import datetime
import pytz
import json
import re

from dateutil.parser              import parse as dateparse
from operator                     import itemgetter

# Django
from django.views.decorators.csrf import csrf_exempt
from django.db.models.functions   import Concat
from django.core.urlresolvers     import reverse
from django.core.exceptions       import SuspiciousOperation
from django.contrib.auth          import logout
from django.db.models             import Q, Value, CharField
from django.shortcuts             import render, HttpResponse
from django.shortcuts             import HttpResponseRedirect
from django.dispatch              import Signal
from django.contrib               import messages
from django.http                  import JsonResponse

from social_django.models import UserSocialAuth

# Project
from .models import Office, Doctor, Patient, Appointment
from .forms  import KioskSetupForm, PatientAppointmentForm, DemographicForm
from .utils  import fstamp, ISO_639, ISO_639_reverse
from .utils  import update_appointment_cache, patch_patient, patch_appointment
from .utils  import seconds_to_text, find_avail_timeslots, model_to_dict
from .utils  import create_appointment, update_patient_cache


api = 'https://drchrono.com/api'


@fstamp
def notify_of_webhook(sender, **kwargs) -> None:
    ''' Whenever something about Appointments and Patients is changed, this
        will be triggered. We'll post the change to our WAMP subscribers
        via a REST bridge
    '''

    model  = kwargs['hook_model'].lower()
    action = kwargs['hook_action'].lower()
    whdata = kwargs['data']['object']
    topic  = 'org.blue_labs.drchrono.{}.{}'.format(model, action)

    try:  # delayed webhooks may try to act on deleted items
        if model == 'appointment':
            obj = Appointment.objects.get(id=whdata['id'])

        elif model == 'patient':
            obj = Patient.objects.get(id=whdata['id'])
    except:  # ignore missing objects
        return

    data = model_to_dict(obj)

    for k in whdata:
        data[k] = whdata[k]

    # now overwrite model with webhook data
    data['owning_doctor_id']       = kwargs['data']['receiver'] \
                                                   ['owning_doctor_id']
    data['scheduled_time_epoch']   = ''
    data['scheduled_time_display'] = ''
    data['arrived_time_display']   = ''
    data['arrived_time_epoch']     = ''

    # masssage data into JSON serializable form as well as pre-build
    # some fields here instead of in javascript
    for k in data:
        print('analyzing key: {}:  d/{}  wh/{}'.format(
            k,
            data[k],
            whdata[k] if k in whdata else '-'))

        if k == 'patient':
            if isinstance(data[k], int):
                obj = Patient.objects.get(id=data[k])
                patient = {
                    'id': obj.id,
                    'first_name': obj.first_name,
                    'last_name': obj.last_name,
                    'patient_photo': obj.patient_photo,
                    'preferred_language_full': ISO_639(obj.preferred_language),
                }
            else:
                patient = {
                    'id': data[k].id,
                    'first_name': data[k].first_name,
                    'last_name': data[k].last_name,
                    'patient_photo': data[k].patient_photo,
                    'preferred_language_full':
                        ISO_639(data[k].preferred_language),
                }

            data[k] = patient

        elif k == 'scheduled_time':
            st_utc = data[k]

            if isinstance(data[k], datetime.datetime):
                st_tz = st_utc.astimezone(pytz.timezone('US/Eastern'))

            elif isinstance(data[k], str):
                st_tz = dateparse(data[k])

            data['scheduled_time_epoch']   = st_tz.strftime('%s')
            data['scheduled_time_display'] = st_tz.strftime('%l:%M%P, ') \
                .lstrip() \
                + str(data['duration'])+'m'

            if isinstance(data[k], datetime.datetime):
                data[k] = data[k].isoformat()

        elif k == 'arrived_time':
            st_utc = data[k]

            if isinstance(data[k], datetime.datetime):
                st_tz = st_utc

            elif isinstance(data[k], str):
                st_tz = dateparse(data[k])

            data['arrived_time_epoch']   = st_tz.strftime('%s')
            data['arrived_time_display'] = st_tz.strftime('%l:%M%P').lstrip()

            if isinstance(data[k], datetime.datetime):
                data[k] = data[k].isoformat()

        elif k == 'reason':
            data[k] = re.sub(r'^#\w+\s*', '', data[k]) if data[k] else ''

        elif isinstance(data[k], datetime.datetime):
            data[k] = int(data[k].timestamp())
        elif isinstance(data[k], datetime.date):
            data[k] = data[k].isoformat()
        elif data[k] is None:
            data[k] = ''
        elif data[k] is 'blank':
            data[k] = ''

    print('==> {}'.format({'topic': topic, 'args': [data]}))

    r = requests.post("https://drc.blue-labs.org:7998/rest-bridge",
                      json={
                          'topic': topic,
                          'args': [data]
                      })

    r.raise_for_status()


webhook_s = Signal(providing_args=['hook_model', 'hook_action', 'data'])
webhook_s.connect(notify_of_webhook)


@csrf_exempt
@fstamp
def webhook(request: requests.request) -> JsonResponse:
    ''' API callback mechanism. Generally, updates our local cache and pushes
        messages to the REST bridge for WAMP publication
    '''

    for k, v in request.META.items():
        print('whk  {:>40}: {}'.format(k, v))

    secret_token = 'e5bffb72d83c9b52cc1e5ade29cd331657830bef63101f4b74cf005256b847ae'

    if len(request.body) == 0:
        print('webhook w/ no body, either a ping, verification, or stranger')

        # unfortunately drchrono API doesn't VERIFY or PING with the
        # secret token so we have to hard code their IP before blindly
        # answering with our secret token
        # !!
        if request.META.get('HTTP_X_FORWARDED_FOR') == '146.20.141.242':
            return JsonResponse({'secret_token': secret_token})

        return JsonResponse({'hi': ':-)'})

    if not request.META.get('HTTP_X_DRCHRONO_SIGNATURE') == secret_token:
        print('unrecognized sender, dropping')
        return HttpResponse("i don't know you", status=401)

    event: str = request.META.get('HTTP_X_DRCHRONO_EVENT')
    data: dict = json.loads(request.body)
    print('Received webhook for: {}'.format(event))

    for obj in data:
        print('  {}'.format(obj))
        for k, v in data[obj].items():
            print('    {:>30}: {}'.format(k, v))

    ds = {'owning_doctor_id': None, 'office': None, 'patient': None}
    for mk, k in (('receiver', 'owning_doctor_id'),
                  ('object', 'office'),
                  ('object', 'patient'),
                  ('object', 'id')):
        try:
            ds[k] = data[mk].get(k, -1)
        except:
            pass

    # TODO, make these item specific granularity, no need to refetch
    # the entire collection
    for k, v in ds.items():
        print('ds> {:>30}: {}'.format(k, v))

    # done
    if event.startswith('APPOINTMENT_'):
        update_appointment_cache(request, doctor=ds['owning_doctor_id'],
                                          office=ds['office'],
                                          get_specific=ds['id'])

    # not receiving PATIENT webhooks from the API...
    elif event.startswith('PATIENT_'):
        update_patient_cache(request, doctor=ds['owning_doctor_id'],
                                      office=ds['office'],
                                      patient=ds['patient'])

    elif event.startswith('VACCINE_'):
        update_patient_cache(request, doctor=ds['owning_doctor_id'],
                                      office=ds['office'],
                                      patient=ds['patient'])

    hook_action, hook_model = [s[::-1] for s in event[::-1].split('_', 1)]
    webhook_s.send(sender=None,
                   hook_model=hook_model,
                   hook_action=hook_action,
                   data=data)

    return JsonResponse({'hi': 'tyty'})


@fstamp
def home(request: requests.request) -> HttpResponse:
    ''' Doctor; kiosk office choice and interface path. The doctor chooses
        which office this tablet is running in. Two buttons then offer to
        run the tablet in Doctor mode; showing appointments for today, and
        Kiosk mode, letting patients check in. Form submission will POST
        to kiosk_path() which will redirect to the doctor or kiosk $home
    '''

    request.session['doctor'] = (
        Doctor
            .objects
            .get(user=UserSocialAuth.objects.get().user).id
    )

    data = {
        'offices': Office.objects.all(),
        'form': KioskSetupForm()
    }

    return render(request, 'home.html', data)


@fstamp
def kiosk_path(request: requests.request) -> HttpResponseRedirect:
    ''' This is an interstitial that collects the POST data for the office
        selection and starts the tablet in either Doctor or Kiosk mode.

        TODO: put the cache priming fully behind WAMP for asynchronous
        updates that don't block the startup
    '''

    if not request.method == 'POST':
        raise SuspiciousOperation

    request.session['office']: int = int(request.POST['office'], 10)

    doctor = request.session['doctor']
    office = request.session['office']

    update_patient_cache(request, get_all=True,
                         doctor=doctor, office=office)

    update_appointment_cache(request, get_all=True,
                             doctor=doctor, office=office)

    path: str = request.POST['path']

    if path not in ('dr_home', 'kiosk_home'):
        return HttpResponseRedirect(reverse('home'))

    return HttpResponseRedirect(reverse(path))


@fstamp
def dr_home(request: requests.request) -> HttpResponse:
    ''' Displays a list of options for the doctor mode...
        as in, for now, just "appointments" ;-)
    '''
    # print info useful for debug
    print(request.POST)
    return render(request, 'drchrono/home.html')


@fstamp
def dr_logout(request: requests.request) -> HttpResponse:
    ''' Tada! byebye
    '''
    logout(request)
    return render(request, 'drchrono/logout.html')


@fstamp
def dr_appointments(request: requests.request) -> HttpResponse:
    ''' Build a list of appointments for today and prepare it as a dictionary
        for the Appointments template to populate
    '''

    now = datetime.datetime.now(pytz.utc) \
                           .astimezone(pytz.timezone('US/Eastern')) \
                           .replace(hour=0, minute=0, second=0, microsecond=0)

    waittimes = [(o.seen_time - o.arrived_time).total_seconds() for o in
                Appointment.objects.all()
                    if o.scheduled_time
                        and o.seen_time
                        and isinstance(o.arrived_time, datetime.datetime)]

    data = [model_to_dict(o) for o in
                Appointment.objects
                    .filter(scheduled_time__date=now)
                    .order_by('scheduled_time')]

    for o in data:
        if o['seen_time']:
            o['wait_time_seconds'] = int(
                    (o['seen_time'] - o['arrived_time']).total_seconds()
                )

            o['wait_time_display'] = seconds_to_text(
                    (o['scheduled_time'] - o['seen_time']).total_seconds()
                )

    print(data)

    return render(
        request,
        'drchrono/appointments.html',
        {
         'appointments':  data,
         'today_date':    now.astimezone(pytz.timezone('US/Eastern'))
                             .strftime('%F'),
         'today':         now.astimezone(pytz.timezone('US/Eastern'))
                             .strftime('%A, %B %e'),
         'waittimes_sum': int(sum(waittimes)),
         'waittimes_len': len(waittimes),
        }
    )


@fstamp
def dr_appointments_refresh(request: requests.request) -> JsonResponse:
    ''' Let the doctor manually refresh the cached appointments and patients.
        This isn't necessary now that WAMP callbacks are implemented.
    '''

    doctor = request.session['doctor']
    office = request.session['office']

    update_patient_cache(request, get_all=True,
                         doctor=doctor, office=office)

    update_appointment_cache(request, get_all=True,
                             doctor=doctor, office=office)

    return JsonResponse({'hi': 'tyty'})


@fstamp
def kiosk_home(request: requests.request) -> HttpResponse:
    ''' Doctor sets the operating mode of the instance, appointment page for
        themself, or kiosk for patient check-in
    '''
    return render(request, 'kiosk/home.html')


@fstamp
def kiosk_check_in(request: requests.request) -> HttpResponse:
    ''' Landing page for patients, simple button to start the check-in process
    '''
    return render(request, 'kiosk/check_in.html')


@fstamp
def kiosk_demographics(request: requests.request) -> HttpResponse:
    ''' Patient has provided their demographic data after check-in, extract
        approved changes and push to the API. Directs the kiosk tablet to an
        interstitial page that displays a simple 'Thank you' then redirects
        to the front Patient Check-In page
    '''

    if not request.method == 'POST':
        raise SuspiciousOperation

    print(request.POST)
    first_name: str = request.POST.get('first_name')
    last_name: str  = request.POST.get('last_name')
    dob: str        = request.POST['date_of_birth']
    dob             = dateparse(dob).strftime('%F')

    form = DemographicForm(request.POST)
    if not form.is_valid():
        print('form complaint :-]')

        # TODO: issue a proper reject, needs some AJAX'ery on the
        # form instead of form.submit()
        raise SuspiciousOperation

    query = Q(first_name__exact=first_name)
    query.add(Q(last_name__exact=last_name), Q.AND)
    query.add(Q(date_of_birth=dob), Q.AND)

    patchdata = {}

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
            for k, v in p:
                print('  {:>30}: {}'.format(k, v))
            print()

        messages.error(request, 'Error: Multiple instances of you in database,'
                                ' please see receptionist to check in')

        return HttpResponseRedirect(reverse('kiosk_check_in'))

    except Patient.DoesNotExist:
        print('Creating a new patient: {}'.format(request.POST))
        patient = Patient(
                first_name=first_name,
                last_name=last_name,
                date_of_birth=dob
            )

        patchdata = {
                'last_name': last_name,
                'first_name': first_name,
                'date_of_birth': dob
            }

        # TODO put in remainder of parameters required by API

    # populate the remainder of patch data by iterating the existing patient
    # fields and overwriting with changes. store only changes in patchdata.

    # this could (should?) be done with form validation but I want to massage
    # some of this data. TODO
    pt_d = model_to_dict(patient)
    for k, v in pt_d.items():

        # only a supervised change allowed. TODO, detect if these were
        # changed and emit an error indication to kiosk
        if k in ('id', 'last_name', 'first_name', 'date_of_birth'):
            continue

        rp_v = request.POST.get(k)

        if rp_v in ('blank', None):
            continue

        if rp_v == '' and v == 'blank':
            continue

        if rp_v != v:
            # see note in utils.py for this function :-(
            if k == 'preferred_language':
                rp_v = ISO_639_reverse(rp_v)

            print('UPDATE: {}, {!r} <> {!r}'.format(k, v, rp_v))
            patchdata[k] = rp_v

            setattr(patient, k, rp_v)  # <-+-- necesssary for local sync
                                       #   |   because we don't get webhook
    patient.save()        # <--------------/   events for patient changes

    try:
        patch_patient(request, patient.id, patchdata)
    except Exception as e:
        print('failed to store demographic update: {}'.format(e))

    # because the API isn't sending me any webhooks other than APPOINTMENT_*
    # let's push this manually. unfortunately this [currently] means that
    # our local Model will be out of sync with what we just pushed to the
    # API as we trigger Model sync on webhook receipt
    data = {
            'object': model_to_dict(patient),
            'receiver': {'owning_doctor_id': request.session['doctor']}
        }

    webhook_s.send(sender=None,
                   hook_model='PATIENT',
                   hook_action='MODIFY',
                   data=data)

    doctor = request.session['doctor']
    doctor = Doctor.objects.get(id=doctor)

    return render(request, 'kiosk/checked_in.html', {'doctor': doctor})


# @fstamp
# def kiosk_checked_in(request: requests.request) -> HttpResponse:
#     '''
#     '''

#     if not request.method == 'POST':
#         raise SuspiciousOperation

#     doctor = request.session['doctor']
#     doctor = Doctor.objects.get(id=doctor)

#     return render(request, 'kiosk/checked_in.html', {'doctor': doctor})


@fstamp
def see_patient(request: requests.request) -> JsonResponse:
    ''' AJAX endpoint called when the 'see patient' checkbox is [un]checked.
        Mark the appointment status as indicated. Try to retain the previous
        status if the box is unchecked (undo accidentally check)
    '''

    if not request.method == 'POST':
        raise SuspiciousOperation

    id: int     = request.POST.get('id')
    status: str = request.POST.get('status')

    # do a little inline f() so we can neatly wrap both the status update
    # and patch job into one try/except
    def __set_status(id: int, status: str) -> str:
        appt = Appointment.objects.get(id=id)

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

    try:
        status = __set_status(id, status)
        patch_appointment(request, id, {'status': status})
        return JsonResponse({'status': status})

    except Exception as e:
        return JsonResponse({'status': 'failed {}'.format(e)})


@fstamp
def autocomplete(request: requests.request) -> HttpResponse:
    ''' AJAX endpoint called when patient is typing their name into the name
        box. Attempt to match either the first, last, or full name
    '''

    callback: str = request.GET.get('callback')
    name: str     = request.GET.get('term').lower()

    qs = Patient.objects.annotate(
                full_name=Concat(
                    'first_name',
                    Value(' '),
                    'last_name',
                    output_field=CharField()
                )
            ).filter(Q(full_name__icontains=name) |
                     Q(first_name__icontains=name) |
                     Q(last_name__icontains=name)
            ).order_by('first_name')

    # ensure the generated name list has unique entries. it doesn't matter at
    # this point if there are two "David Ford" patients, we only need one of
    # them in this list
    results = sorted(set([str(o).replace('  ', ' ') for o in qs]))

    response_prose = '{}({{result:{}}})'.format(callback, results)
    return HttpResponse(response_prose, "text/javascript")


@fstamp
def appointments(request: requests.request) -> HttpResponse:
    ''' Provide a list of appointment times matching this patient. Ensure a
        walk-in button dataset is included in the list
    '''

    if not request.method == 'GET':
        raise SuspiciousOperation

    callback: str = request.GET.get('callback')
    name: str     = request.GET.get('name').lower().replace('  ', ' ')

    print('name: {}'.format(name))

    # default results
    forever = pytz.timezone('UTC').localize(datetime.datetime(2038, 12, 31))
    results = [[-1, forever, "I want a walk-in appointment"]]

    now = datetime.datetime.now(pytz.utc) \
                           .astimezone(pytz.timezone('US/Eastern')) \
                           .replace(hour=0, minute=0, second=0, microsecond=0)

    while True:  # abuse this so we can jump out of processing when we please
        try:
            dob = dateparse(request.GET['dob']).strftime('%F')
        except:  # TODO, we could be more friendly and emit an indication for the
                 # AJAX operation so it could perhaps highlight the dob field and
                 # have the patient make corrections
            print('invalid DoB')
            break

        queryset = Patient.objects.annotate(search_name=Concat('first_name',
                                                               Value(' '),
                                                               'last_name'))
        try:
            patient = queryset.get(search_name__iexact=name, date_of_birth=dob)
        except Patient.DoesNotExist:
            # probably a new patient walk-in, could possibly be a name typo.
            # TODO we don't handle new patients yet
            print('unknown patient')
            break

        query = Q(scheduled_time__date=now)
        query.add(Q(patient__id=patient.id), Q.AND)

        try:
            data = [o for o in Appointment.objects
                            .filter(query)
                            .order_by('scheduled_time', 'patient__first_name')]

        except Appointment.DoesNotExist:
            # probably a walk-in
            print('no appointment listed today for this patient')
            break

        # build as a list of tuples first...
        results = [(o.id, o.scheduled_time, o.scheduled_time
                    .astimezone(pytz.timezone('US/Eastern'))
                    .strftime('%l:%M%P')
                    .strip()) for o in data]

        # so they are guaranteed unique...
        results = set(results)

        # then make it a list of lists because javascript has no notion of
        # tuples and we're building the json by hand
        results = sorted(results, key=itemgetter(1))
        break

    # we used the while: to break out in order to mutate the results before
    # sending off in a JSON packet
    results = [[a, c] for a, b, c in results]
    prose_f = f'{callback}({{result:{results}}})'
    return HttpResponse(prose_f, "text/javascript")


@fstamp
def walkin_find_avail_time(request: requests.request) -> HttpResponse:
    ''' Try to find the next available time slot for a walk-in appointment.
        This may yield an empty list if the doc is full-up
    '''

    if not request.method == 'GET':
        raise SuspiciousOperation

    now = datetime.datetime.now(pytz.utc) \
                           .astimezone(pytz.timezone('US/Eastern')) \
                           .replace(hour=0, minute=0, second=0, microsecond=0)

    callback: str = request.GET.get('callback')

    query = Q(scheduled_time__date=now)
    schedule = [(o.scheduled_time, o.duration) for o in Appointment
                                                  .objects
                                                  .filter(query)
                                                  .order_by('scheduled_time')]
    slots = find_avail_timeslots(schedule)

    # localize into tuples of (time, duration)
    slots = [(t.astimezone(pytz.timezone('US/Eastern')), d)
             for t, d in slots]

    results = ['{} for {} minutes'.format(t.strftime('%l:%M%P'), d).strip()
               for t, d in slots]

    prose_f = f'{callback}({{result:{results}}})'
    return HttpResponse(prose_f, "text/javascript")


@fstamp
def appointment_create(request: requests.request) -> JsonResponse:
    ''' Patient has requested a walk-in appointment, create it
    '''

    if not request.method == 'POST':
        raise SuspiciousOperation

    print(request.POST)
    name: str = request.POST.get('name').lower()
    appt: str = request.POST.get('appointment_time')
    dob: str  = request.POST.get('dob')
    now  = datetime.datetime.now(pytz.utc) \
                            .astimezone(pytz.timezone('US/Eastern')) \
                            .replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        dob = dateparse(dob).strftime('%F')

        appt_time = dateparse(appt.split()[0])
        appt_time = now.replace(hour=appt_time.hour, minute=appt_time.minute)
        print('appt time: {}'.format(appt_time))

    except:
        print("no-go buster, we don't support funny times yet")
        raise SuspiciousOperation

    # verify the patient exists in our DB
    queryset = Patient.objects.annotate(search_name=Concat('first_name',
                                                           Value(' '),
                                                           'last_name'))
    try:
        patient = queryset.get(search_name__iexact=name,
                               date_of_birth=dob)

    except Patient.DoesNotExist:
        return JsonResponse({'status': 'unknown patient'})

    # create appt
    create_appointment(request, patient, scheduled_time=appt_time,
                       is_walk_in=True, duration=30)

    # return appt id ...but wait, there's more! actually, there isn't. The
    # API doesn't give us an ID when a new appointment is made. we'll only
    # get that in our webhook
    return JsonResponse({'status': 'tyty'})


@fstamp
def check_in(request: requests.request) -> JsonResponse:
    ''' Patient correctly identified self and selected their appointment
        time. Mark them checked in with the API
    '''

    if not request.method == 'POST':
        raise SuspiciousOperation

    now = datetime.datetime.now(pytz.utc) \
                           .astimezone(pytz.timezone('US/Eastern')) \
                           .replace(hour=0, minute=0, second=0, microsecond=0)

    print(request.POST)
    name: str = request.POST.get('name').lower()
    appt: int = int(request.POST.get('appointment_id'), 10)
    dob: str  = request.POST.get('dob')
    dob       = dateparse(dob).strftime('%F')

    form = PatientAppointmentForm({
        'id': appt,
        'name': name,
        'date_of_birth': dob
        })

    if not form.is_valid():
        print('form data invalid: {}'.format(form.errors))
        raise SuspiciousOperation(form.errors)

    if appt == -1:  # walk-in appointments have an id of -1
        appt_time: str = request.POST.get('appointment_time')
        appt_time = dateparse(appt_time.split()[0])
        appt_time = now.replace(hour=appt_time.hour, minute=appt_time.minute)
        print('appointment_time is {}'.format(appt_time))

        # note, this is currently a race-condition and relies on
        # our webhook giving us the new appointment ASAP. the API
        # does not give us an ID in the response when we create a
        # new appointment. there are a few complex work-arounds
        # that we can do that rely on a chain of events, but right
        # now, it's just a 5 second delay :-(

        # an unfound patient/appt isn't handled

        print('finding their walk-in appointment')
        # try and locate
        q = Patient.objects.annotate(
                full_name=Concat(
                    'first_name',
                    Value(' '),
                    'last_name',
                    output_field=CharField()
                )
            ).filter(Q(date_of_birth=dob) &
                     Q(full_name__icontains=name)
            ).order_by('first_name')

        try:
            q.get()
        except Patient.DoesNotExist:
            print('not so good, this should be a confirmed patient')
        except Patient.MultipleObjectsReturned:
            print('not so good, this should be only one patient')
        else:
            a = Appointment.objects.filter(scheduled_time=appt_time).get()

    else:
        id = form.cleaned_data.get('id')
        a = Appointment.objects.get(id=id)

    # the Project email indicates we should set this to "Arrived", but
    # Checked In does seem quite a bit more appropriate
    a.status = 'Checked In'
    a.arrived_time = datetime.datetime.now(pytz.utc)
    a.save()

    patch_appointment(request, a.id, {'status': a.status})

    return JsonResponse({'hi': 'tyty'})


@fstamp
def demographics(request: requests.request) -> HttpResponse:
    ''' AJAX endpoint, the patient has checked in and the demographics block
        needs to be populated with existing data so the patient can make any
        appropriate changes
    '''
    if not request.method == 'GET':
        raise SuspiciousOperation

    callback: str = request.GET.get('callback')
    name: str     = request.GET.get('name').lower()

    while True:
        try:
            dob: str = request.GET['dob']
            dob = dateparse(dob).strftime('%F')
        except:
            results = ["Bad date of birth"]
            break

        queryset = Patient.objects.annotate(search_name=Concat('first_name',
                                                               Value(' '),
                                                               'last_name'))
        try:
            patient = queryset.get(search_name__iexact=name,
                                   date_of_birth=dob)
        except Patient.DoesNotExist:
            # probably a walk-in, they'll just need to supply us with
            # pertinent info :)
            results = ["Patient not Found"]
            break

        r1 = {k: v for k, v in patient if k not in ('id',)}
        results = {}
        for k, v in r1.items():
            if k == 'date_of_birth':
                v = v.strftime('%F')
            elif v in (None, 'blank'):
                v = ''
            results[k] = v
        break

    prose_f = f'{callback}({{result:{results}}})'
    print(prose_f)
    return HttpResponse(prose_f, "text/javascript")
