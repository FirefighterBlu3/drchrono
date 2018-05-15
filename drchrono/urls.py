from django.conf.urls import include, url
from django.views.generic import TemplateView
from django.contrib import admin

from . import views


urlpatterns = [
    url(r'^admin/', include(admin.site.urls)),
    url(r'^$', TemplateView.as_view(template_name='index.html'), name='index'),

    # todo, split these into sep. apps in /doctor, /kiosk, etc
    # name=foo is what {% url 'foo' %} is matched for template code
    # named patterns are needed for reversing

    url(r'^home/$',                views.home,                  name='home'),
    url(r'^webhook/$',             views.webhook,               name='webhook'),
    url(r'^ajax/see-patient/$',    views.ajax_see_patient,      name='ajax_see_patient'),
    url(r'^ajax/checkin/autocomplete/$', views.ajax_checkin_autocomplete, name='ajax_checkin_autocomplete'),
    url(r'^ajax/checkin/appointments/$', views.ajax_checkin_appointments, name='ajax_checkin_appointments'),
    url(r'^ajax/checkin/complete/$', views.ajax_checkin_complete, name='ajax_checkin_complete'),
    url(r'^ajax/checkin/demographics/$', views.ajax_checkin_demographics, name='ajax_checkin_demographics'),
    url(r'^ajax/walkin/find_time/$', views.ajax_walkin_find_avail_time, name='ajax_walkin_find_avail_time'),
    url(r'^kiosk_path/$',          views.kiosk_path,            name='kiosk_path'),
    url(r'^doctor/home/$',         views.drchrono_home,         name='drchrono_home'),
    url(r'^doctor/login/$',        views.drchrono_login,        name='drchrono_login'),
    url(r'^doctor/logout/$',       views.drchrono_logout,       name='drchrono_logout'),
    url(r'^doctor/appointments/$', views.drchrono_appointments, name='drchrono_appointments'),
    url(r'^kiosk/home/$',          views.kiosk_home,            name='kiosk_home'),
    url(r'^kiosk/check_in/$',      views.kiosk_check_in,        name='kiosk_check_in'),
    url(r'^kiosk/checked_in/$',    views.kiosk_checked_in,      name='kiosk_checked_in'),
    url(r'^kiosk/demographics/$',  views.kiosk_demographics,    name='kiosk_demographics'),

    url(r'', include('social_django.urls', namespace='social')),
]
