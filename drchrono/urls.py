from django.conf.urls import include, url
from django.views.generic import TemplateView
from django.contrib import admin

from . import views as v


urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^$', TemplateView.as_view(template_name='index.html'), name='index'),

    # todo, split these into sep. apps in /doctor, /kiosk, etc
    # name=foo is what {% url 'foo' %} is matched for template code
    # named patterns are needed for reversing

    url(r'^home/$',                            v.home,                    name='home'),
    url(r'^webhook/$',                         v.webhook,                 name='webhook'),
    url(r'^ajax/checkin/autocomplete/$',       v.autocomplete,            name='autocomplete'),
    url(r'^ajax/checkin/appointments/$',       v.appointments,            name='appointments'),
    url(r'^ajax/checkin/appointment/create/$', v.appointment_create,      name='appointment_create'),
    url(r'^ajax/checkin/check_in/$',           v.check_in,                name='check_in'),
    url(r'^ajax/checkin/demographics/$',       v.demographics,            name='demographics'),
    url(r'^ajax/find_walkin_tm/$',             v.walkin_find_avail_time,  name='walkin_find_avail_time'),
    url(r'^kiosk_path/$',                      v.kiosk_path,              name='kiosk_path'),
    url(r'^dr/home/$',                         v.dr_home,                 name='dr_home'),
    url(r'^dr/logout/$',                       v.dr_logout,               name='dr_logout'),
    url(r'^dr/appointments/$',                 v.dr_appointments,         name='dr_appointments'),
    url(r'^dr/appointments/refresh/$',         v.dr_appointments_refresh, name='dr_appointments_refresh'),
    url(r'^dr/see-patient/$',                  v.see_patient,             name='see_patient'),
    url(r'^kiosk/home/$',                      v.kiosk_home,              name='kiosk_home'),
    url(r'^kiosk/check_in/$',                  v.kiosk_check_in,          name='kiosk_check_in'),
    # url(r'^kiosk/checked_in/$',                v.kiosk_checked_in,        name='kiosk_checked_in'),
    url(r'^kiosk/demographics/$',              v.kiosk_demographics,      name='kiosk_demographics'),

    url(r'', include('social_django.urls', namespace='social')),
]
