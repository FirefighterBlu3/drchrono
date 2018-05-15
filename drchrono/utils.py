from django.db.models import ForeignKey
from social_django.models import UserSocialAuth

from .models import Office, Doctor, Patient, Appointment

import requests
import pycountry
import datetime
import functools
import inspect
import pytz
import re

from functools import wraps
from operator import itemgetter
from dateutil.parser import parse as dateparse

api='https://drchrono.com/api'


def fstamp(f):
    ''' just print a path.to.module.function() to trace flow
    '''
    @wraps(f)
    def __wrapper__(*args, **kwargs):
        print('\x1b[1;36m{}.{}()\x1b[0m'.format(__name__,f.__name__))
        return f(*args, **kwargs)

    return __wrapper__


def check_refresh_token(f):
    ''' decorator to apply to all API calling functions
    '''
    @wraps(f)
    def __wrapper__(*args, **kwargs):
        # check if our session has expired
        user = UserSocialAuth.objects.get()
        extra_data    = user.extra_data
        refresh_token = extra_data['refresh_token']
        auth_time     = datetime.datetime.fromtimestamp(extra_data['auth_time'])
        expires_in    = datetime.timedelta(extra_data['expires_in'])
        expires_time  = auth_time + expires_in

        print('ed: {}'.format(extra_data))
        if datetime.datetime.now() > expires_time:
            print('need to refresh our token')
            # so do it...
            x = user.refresh_token(refresh_token)
            print(x)
        else:
            print('not refreshing token')

        return f(*args, **kwargs)

    return __wrapper__


@check_refresh_token
def json_get(url: str, params=None, headers=None):
    data=[]
    while url:
        print('retrieving: {} params: {}'.format(url, params))
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        d = response.json()
        data += d['results']
        url = d['next']

    return data


def ISO_639(key: str):
    if key in (None, '', 'blank'):
        key='eng'

    key = key.lower()

    try:
        lang = pycountry.languages.get(alpha_3=key).name
    except:
        lang = '<unknown: {}>'.format(key)

    return lang


def model_to_dict(instance):
    data = {}
    for field in instance._meta.fields:
        data[field.name] = field.value_from_object(instance)
        if isinstance(field, ForeignKey):
            data[field.name] = field.rel.to.objects.get(pk=data[field.name])
    return data


def seconds_to_text(s: int):
    h = str(int(s/60/60%24))
    m = str(int(s/60%60))
    s = str(int(s%60))
    return ':'.join((h,m,s))


def update_patient_cache(request, get_all: bool =False):
    ''' cache priming setup; as the application runs, the WAMP module
        ought to append/update/delete single items as they occur
    '''
    access_token = UserSocialAuth.objects.get().extra_data['access_token']
    headers      = {'Authorization': 'Bearer %s' % access_token,}
    doctor       = request.session['doctor']
    office       = request.session['office']

    # sync patients based on those that have an appointment at the specified office for the
    # specified doctor, then sync appointments
    data={
        'doctor':  doctor,
        'offices': office
        }

    if get_all: # rarely true
        del data['offices']

    print('Fetching all patients')
    patients = json_get(api+'/patients', params=data, headers=headers)

    print('Priming cache for {} patients'.format(len(patients)))
    for i,p in enumerate(patients):
        if not i % 10:
            print('  {}'.format(i))

        try:
            pt = Patient.objects.get(id=p['id'])
        except Patient.DoesNotExist:
            pt = Patient(
                    id = p['id'],
                )
        finally:
            pt.first_name                 = p['first_name']
            pt.last_name                  = p['last_name']
            pt.middle_name                = p['middle_name']
            pt.date_of_birth              = p['date_of_birth']
            pt.ethnicity                  = p['ethnicity']
            pt.race                       = p['race']
            pt.social_security_number     = p['social_security_number']
            pt.gender                     = p['gender']
            pt.address                    = p['address']
            pt.city                       = p['city']
            pt.state                      = p['state']
            pt.zip_code                   = p['zip_code']
            pt.cell_phone                 = p['cell_phone']
            pt.email                      = p['email']
            pt.emergency_contact_name     = p['emergency_contact_name']
            pt.emergency_contact_phone    = p['emergency_contact_phone']
            pt.emergency_contact_relation = p['emergency_contact_relation']
            pt.preferred_language         = p['preferred_language']
            pt.patient_photo              = p['patient_photo']
            pt.save()
            print('Patient cache updated: {}/{} {}'.format(pt.id, pt, pt.date_of_birth))

    if get_all:
        # delete any patients in our local db that doesn't exist in the API response
        print('Primed {} patients'.format(len(patients)))
        oids=[o['id'] for o in patients]

        for o in Patient.objects.all():
            if not o.id in oids:
                print('Flushing unknown patient {}/{}'.format(o.id, o))
                o.delete()


def update_appointment_cache(request, get_all: bool =False, get_specific: bool =False):
    ''' cache priming setup; as the application runs, the WAMP module
        ought to append/update/delete single items as they occur
    '''
    access_token = UserSocialAuth.objects.get().extra_data['access_token']
    headers      = {'Authorization': 'Bearer %s' % access_token,}
    doctor       = request.session['doctor']
    office       = request.session['office']

    # when making a GET request to /api/appointments either the
    #   since, date, or date_range query parameter must be specified
    # note; this is based on the principal doctor of the facility, other
    # doctors may be operating underneath him/her
    now = datetime.datetime.now(pytz.utc).astimezone(pytz.timezone('US/Eastern'))
    print('Fetching appointment schedule for: {}'.format(now))

    data = {
        'doctor': request.session['doctor'],
        'office': request.session['office'],
        'date'  : now.strftime('%F'),
    }

    if get_all: # rarely true
        del data['office']
        del data['date']
        data['since'] = '1970-01-01'

    print('Fetching all appointments')
    appointments = json_get(api+'/appointments', params=data, headers=headers)

    appointments = sorted(appointments, key=itemgetter('scheduled_time'))

    print('Priming cache for {} appointments'.format(len(appointments)))
    for i, appt in enumerate(appointments):
        if not i % 10:
            print('  {}'.format(i))

        try:
            p = Patient.objects.get(id=appt['patient'])
        except Patient.DoesNotExist:
            update_patient_cache(request)
            try:
                p = Patient.objects.get(id=appt['patient'])
            except Patient.DoesNotExist:
                s='Appointment patient ({}) does not exist'.format(appt['patient'])
                raise ValueError(s)

        try:
            a = Appointment.objects.get(id=appt['id'])
        except Appointment.DoesNotExist:
            print('creating new appointment')
            a = Appointment(
                    id = appt['id'],
                )
        finally:
            a.scheduled_time          = pytz.timezone('US/Eastern').localize(dateparse(appt['scheduled_time']))
            a.patient                 = p
            a.duration                = appt['duration']
            a.reason                  = re.sub('^#\w+\s*', '', appt['reason'])
            a.status                  = appt['status'] or ''
            a.exam_room               = appt['exam_room']
            a.preferred_language_full = ISO_639(p.preferred_language)
            a.save()
            #print('Appointment cache updated: {}/{} {}'.format(
            #    a.scheduled_time.strftime('%F %T'),p,p.date_of_birth))

    if get_all:
        print('Primed {} appointments'.format(len(appointments)))
        oids=[int(o['id'], 10) for o in appointments]

        for o in Appointment.objects.all():
            if not o.id in oids:
                print('Flushing unknown appointment {}/{}'.format(o.id, o))
                o.delete()


@check_refresh_token
def patch_appointment(request, appointment_id: int, patchdata):
    access_token = UserSocialAuth.objects.get().extra_data['access_token']
    headers      = {'Authorization': 'Bearer %s' % access_token,}
    doctor       = request.session['doctor']
    office       = request.session['office']

    url = api+'/appointments/{}'.format(appointment_id)
    print('patching API: {}, to {}'.format(url, patchdata))

    response = requests.patch(url, data=patchdata, headers=headers)
    response.raise_for_status()

    print(response)


@check_refresh_token
def create_appointment(request, patient, scheduled_time, duration: int =None, reason: str =None, is_walk_in: bool =False, exam_room: int =None, status: str =None):
    ''' Initial version of this, we can't fill in a number of things yet
        as we aren't using appointment profiles and the only caller of
        this presently, is a patient walk-in
    '''
    access_token = UserSocialAuth.objects.get().extra_data['access_token']
    headers      = {'Authorization': 'Bearer %s' % access_token,}
    doctor       = request.session['doctor']
    office       = request.session['office']

    url = api+'/appointments'

    patchdata = {
        'doctor':         doctor,                 # required
        'duration':       duration or 30,         # required (if no profile)
        'exam_room':      exam_room or 0,         # required
        'office':         office,                 # required
        'patient':        patient.id,             # required
        'scheduled_time': scheduled_time,         # required
        'is_walk_in':     is_walk_in,
        'reason':         reason or '',
        'status':         status or '',
    }

    print('patching API: {}, to {}'.format(url, patchdata))
    response = requests.post(url, data=patchdata, headers=headers)
    response.raise_for_status()
    print(response.body)


def find_avail_timeslots(schedule, skip=None):
    # normally "now" will be calculated
    #now = datetime.datetime.now(pytz.utc)
    now = datetime.datetime.now(pytz.utc).replace(hour=12, minute=27)

    min_duration = datetime.timedelta(minutes=30)
    max_start_time = now.replace(hour=16, minute=0, second=0, microsecond=0)

    # lunch hour etc
    if skip:
        schedule += skip
        schedule.sort()

    avail = []

    for i, (s, d) in enumerate(schedule):
        # check if 'now' is before the current timeslot
        if now < s and (s-now) > min_duration:
            if i==0:
                avail_t = now
            else:
                avail_t, t_d = schedule[i-1]
                avail_t += datetime.timedelta(minutes=t_d)

            if avail_t > max_start_time:
                continue

            # find duration, skip this slot if less than the minimum
            avail_d = s - avail_t
            if avail_d < min_duration:
                continue

            # only give the PT 30 minutes by default
            avail_d = min_duration

            avail.append((avail_t, int(avail_d.total_seconds()/60) ))

    return avail
