import requests
import pycountry
import datetime
import inspect
import pytz
import re

from functools import wraps
from operator import itemgetter
from dateutil.parser import parse as dateparse

from django.db.models import ForeignKey
from social_django.models import UserSocialAuth
from django.utils import timezone

from .models import Doctor, Patient, Appointment


api = 'https://drchrono.com/api'


def fstamp(f):
    ''' just print a path.to.module.function() to trace flow
    '''
    @wraps(f)
    def __wrapper__(*args, **kwargs):
        module_ = inspect.unwrap(__wrapper__).__module__
        function_ = f.__name__
        print('\x1b[1;36m{}.{}()\x1b[0m'.format(module_, function_))
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
def json_get(url: str, params=None, headers=None) -> dict:
    data = []

    while url:
        print('retrieving: {} params: {}'.format(url, params))
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        d = response.json()

        if 'results' in d:
            data += d['results']
            url = d['next']
        else:
            # we fetched a single item by id, so build a one-item list
            data = [d, ]
            break

    return data


def ISO_639(key: str) -> str:
    if key in (None, '', 'blank'):
        key = 'eng'

    key = key.lower()

    try:
        lang = pycountry.languages.get(alpha_3=key).name
    except:
        lang = '<unknown: {}>'.format(key)

    return lang


def ISO_639_reverse(key: str) -> str:
    ''' ugly gross hack but this module doesn't support a better way.
        we probably ought to plan on making a <select..> list of languages
        that patients can use instead of a text box
    '''
    try:
        key_long = [l.alpha_3 for l in list(pycountry.languages)
                    if l.name.lower() == key.lower()][0]
    except:
        print('WARNING: Unable to lookup 639-2 for {}'.format(key))
        key_long = ''

    return key_long


def model_to_dict(instance):
    data = {}
    for field in instance._meta.fields:
        data[field.name] = field.value_from_object(instance)
        if isinstance(field, ForeignKey):
            data[field.name] = field.rel.to.objects.get(pk=data[field.name])
    return data


def seconds_to_text(s: int) -> str:
    h = str(int(s / 60 / 60 % 24))
    m = str(int(s / 60 % 60))
    s = str(int(s % 60))
    return ':'.join((h, m, s))


def update_patient_cache(request, get_all: bool = False, doctor: int = None,
                         office: int = None, patient: int = None) -> None:
    ''' cache priming setup; as the application runs, the WAMP module
        ought to append/update/delete single items as they occur
    '''
    access_token = UserSocialAuth.objects.get().extra_data['access_token']
    headers      = {'Authorization': 'Bearer %s' % access_token,}

    if not (doctor and office):
        doctor       = request.session['doctor']
        office       = request.session['office']

    # sync patients based on those that have an appointment at the specified
    # office for the specified doctor, then sync appointments
    data = {
        'doctor':  doctor,
        'offices': office
        }

    if get_all:  # rarely true
        del data['offices']

    print('Fetching all patients')
    patients = json_get(api+'/patients', params=data, headers=headers)
    print(patients)

    print('Priming cache for {} patients'.format(len(patients)))
    for n, p in enumerate(patients):
        if not n % 25:
            print('  {}'.format(n))

        try:
            pt = Patient.objects.get(id=p['id'])
        except Patient.DoesNotExist:
            pt = Patient(
                    id=p['id'],
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
            print('Patient cache updated: {}/{} {}'.format(pt.id,
                                                           pt,
                                                           pt.date_of_birth))

    if get_all:
        # delete any patients in our local db that doesn't exist in the API
        print('Primed {} patients'.format(len(patients)))
        oids = [o['id'] for o in patients]

        for o in Patient.objects.all():
            if o.id not in oids:
                print('Flushing unknown patient {}/{}'.format(o.id, o))
                o.delete()


def update_appointment_cache(request, get_all: bool = False,
                             get_specific: int = None, doctor: int = None,
                             office: int = None) -> None:
    ''' Cache priming setup; as the application runs, the WAMP module
        ought to append/update/delete single items as they occur
    '''
    access_token = UserSocialAuth.objects.get().extra_data['access_token']
    headers      = {'Authorization': 'Bearer %s' % access_token}

    if not (doctor and office):
        doctor = request.session['doctor']
        office = request.session['office']

    # when making a GET request to /api/appointments either the
    #   since, date, or date_range query parameter must be specified
    # note; this is based on the principal doctor of the facility, other
    # doctors may be operating underneath him/her
    now = datetime.datetime.now(pytz.utc) \
                           .astimezone(pytz.timezone('US/Eastern'))

    if get_specific:
        print('Fetching just one appointment: {}'.format(get_specific))

    elif not get_all:
        print('Fetching appointment schedule for: {}'.format(now))

    else:
        print('Fetching all appointments')

    url = api+'/appointments'

    data = {
        'doctor': doctor,
        'office': office,
        'date'  : now.strftime('%F'),
    }

    if get_all:  # rarely true
        del data['office']
        del data['date']
        data['since'] = '1970-01-01'
    elif get_specific:
        del data['date']
        url += '/{}'.format(get_specific)

    try:
        appointments = json_get(url, params=data, headers=headers)
        appointments = sorted(appointments, key=itemgetter('scheduled_time'))
    except:
        print('Aborting; Failed to fetch appt for {}'.format(url))
        return

    print('Updating cache for {} appointments'.format(len(appointments)))
    for i, appt in enumerate(appointments):
        if not i % 25:
            print('  {}'.format(i))

        try:
            p = Patient.objects.get(id=appt['patient'])
        except Patient.DoesNotExist:
            update_patient_cache(request)
            try:
                p = Patient.objects.get(id=appt['patient'])
            except Patient.DoesNotExist:
                s = 'Appointment patient ({}) does not exist'.format(
                    appt['patient'])

                raise ValueError(s)

        try:
            a = Appointment.objects.get(id=appt['id'])
        except Appointment.DoesNotExist:
            print('creating new appointment')
            a = Appointment(
                    id=appt['id'],
                )
        finally:
            a.scheduled_time          = pytz.timezone('US/Eastern') \
                .localize(dateparse(appt['scheduled_time']))

            a.patient                 = p
            a.duration                = appt['duration']
            a.reason                  = re.sub(r'^#\w+\s*', '', appt['reason']) \
                                            if appt['reason'] else ''
            a.status                  = appt['status'] or ''
            a.exam_room               = appt['exam_room']
            a.preferred_language_full = ISO_639(p.preferred_language)
            a.save()

            if get_specific or not get_all:
                print('Appointment cache updated: {} {}/{} {}'.format(
                    a.id, a.scheduled_time.strftime('%F %T'),
                    p, p.date_of_birth))

    if get_all:
        print('Primed {} appointments'.format(len(appointments)))
        oids = [int(o['id'], 10) for o in appointments]

        for o in Appointment.objects.all():
            if o.id not in oids:
                print('Flushing unknown appointment {}/{}'.format(o.id, o))
                o.delete()


@check_refresh_token
def patch_patient(request, patient_id: int, patchdata) -> None:
    ''' Push a change up to the API for patient data
    '''
    access_token = UserSocialAuth.objects.get().extra_data['access_token']
    headers      = {'Authorization': 'Bearer %s' % access_token}

    url = api+'/patients/{}'.format(patient_id)
    print('patching API for patient: {}, to {}'.format(url, patchdata))

    response = requests.patch(url, data=patchdata, headers=headers)
    response.raise_for_status()


@check_refresh_token
def patch_appointment(request, appointment_id: int, patchdata) -> None:
    ''' Push a change up to the API for appointment data
    '''
    access_token = UserSocialAuth.objects.get().extra_data['access_token']
    headers      = {'Authorization': 'Bearer %s' % access_token,}

    url = api+'/appointments/{}'.format(appointment_id)
    print('patching API for appointment: {}, to {}'.format(url, patchdata))

    response = requests.patch(url, data=patchdata, headers=headers)
    response.raise_for_status()


@check_refresh_token
def create_appointment(request, patient, scheduled_time: datetime.datetime,
                       duration: int = None, reason: str = None,
                       is_walk_in: bool = False, exam_room: int = None,
                       status: str = None) -> None:
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
    try:
        response = requests.post(url, data=patchdata, headers=headers)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        # most likely a duplicate, add exact test TODO
        print('conflict? {}'.format(e))
        # delete and re-create appt? but we need the appt ID. we can't
        # handle this yet. we'll probably need to carefully generate a
        # single ID lookup to figure out what appt we're conflicting with
        # then determine what to do. everything about this requires we
        # wait for a webhook to arrive -- which isn't guaranteed :-/

    try:
        print('create appt response body: {}'.format(response.body))
    except:  # TODO ask for an update to API that gives us an ID in response
        pass


def find_avail_timeslots(schedule, skip=None) -> list:
    ''' generate the next 1-2 available time slots for a walk-in.
        this doesn't really work as i want, i'd like to return all
        available time slots
    '''

    # normally "now" will really be now() but this is manually set
    # since I'm usually writing code long after real doctor hours ;-)

    now = pytz.timezone('US/Eastern').localize(
            datetime.datetime.now()
            ).replace(hour=8, minute=27)  # 8.27am

    print('find walk-in time for {}'.format(now))

    min_duration = datetime.timedelta(minutes=30)
    max_start_time = now.replace(hour=16, minute=30, second=0, microsecond=0)

    # lunch hour etc
    if skip:
        schedule += skip
        schedule.sort()

    if len(schedule) > 0:
        print(schedule)
        if max_start_time > schedule[-1][0] \
                + datetime.timedelta(minutes=schedule[-1][1]):
            # place a stop marker to search before
            schedule.append((max_start_time, 0))

    else:
        schedule.append((max_start_time, 0))

    avail = []

    # analyze the existing schedule
    for i, (s, d) in enumerate(schedule):
        # check if 'now' is before the current timeslot
        if now < s and (s-now) > min_duration:
            if i == 0:
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

            avail.append((avail_t, int(avail_d.total_seconds()/60)))

    # now do 30 minute slots from the last scheduled appt to the end of the
    # office day
    # TODO

    return avail
