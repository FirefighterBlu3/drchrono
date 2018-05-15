import os
import pytz
import datetime
import logging
import inspect
#import requests

from dateutil.parser import parse as dateparse

from social_core.backends.oauth import BaseOAuth2
from social_django.models import UserSocialAuth

from drchrono.models import Office, Doctor
from drchrono.utils import fstamp, json_get

api='https://drchrono.com/api'

class drchronoOAuth2(BaseOAuth2):
    """
    drchrono OAuth authentication backend
    """

    name                = 'drchrono'
    AUTHORIZATION_URL   = 'https://drchrono.com/o/authorize/'
    ACCESS_TOKEN_URL    = 'https://drchrono.com/o/token/'
    ACCESS_TOKEN_METHOD = 'POST'
    REDIRECT_STATE      = False
    USER_DATA_URL       = 'https://drchrono.com/api/users/current'
    EXTRA_DATA = [
        ('refresh_token', 'refresh_token'),
        ('expires_in', 'expires_in'),
    ]
    # TODO: setup proper token refreshing
    REFRESH_TOKEN_URL   = ACCESS_TOKEN_URL



    @fstamp
    def get_auth_header(self, access_token):
        #logger = logging.getLogger(__name__)
        #logger.warn("access_token={}".format(access_token))
        return {'Authorization': 'Bearer {0}'.format(access_token)}


    @fstamp
    def user_data(self, access_token, *args, **kwargs):
        """
        Load user data from the service
        """
        logger = logging.getLogger(__name__)
        logger.warn(">> args={} kwargs={}".format(args, kwargs))
        logger.warn(">> {}".format(self.USER_DATA_URL))

        return self.get_json(
            self.USER_DATA_URL,
            headers=self.get_auth_header(access_token)
        )


    @fstamp
    def get_user_details(self, response):
        """
        Return user details from drchrono account
        """

        # this shows our initial scope data, leave it for dbg
        print('response data: {}'.format(response))

        user = UserSocialAuth.objects.get().user

        # store my tokens
        access_token      = response['access_token']
        refresh_token     = response['refresh_token']
        expires_timestamp = datetime.datetime.now(pytz.utc) + \
                            datetime.timedelta(seconds=response['expires_in'])

        # prepare common use data
        headers = {'Authorization': 'Bearer %s' % access_token,}

        # get expanded doctor info; proper name components
        data = json_get(api+'/doctors', headers=headers)
        print('doc_data:{}'.format(data))
        doc_data = [e for e in data if e['id']==response['doctor']][0]

        # get doctor's offices
        office_data = json_get(api+'/offices', headers=headers)
        print('office_data: {}'.format(office_data))

        try:
            doc = Doctor.objects.get(user=user)
        except Doctor.DoesNotExist:
            doc = Doctor(
                    id   = response['doctor'],
                    user = user,
                )
        finally:
            doc.first_name        = doc_data['first_name'],
            doc.last_name         = doc_data['last_name'],
            doc.office            = office_data[0]['id']  # hardwire the first office, TODO
            doc.access_token      = access_token
            doc.refresh_token     = refresh_token
            doc.expires_timestamp = expires_timestamp
            print('Saving doc: {}'.format(user))
            for k,v in doc:
                print('  {:>30}: {}'.format(k,v))

            doc.save()
            print('Doc saved: {}/{} ({})'.format(doc.id, doc, user))


        oids = [o['id'] for o in office_data]

        for e in office_data:
            try:
                office = Office.objects.get(id=e['id'])
            except:
                office = Office(
                        id = e['id']
                    )
            finally:
                office.name         = e['name']
                office.address      = e['address']
                office.phone_number = e['phone_number']
                office.save()

            print('Office loaded: {}'.format(office.name))

        # delete any offices in our local db that doesn't exist in the API
        for o in Office.objects.all():
            if not o.id in oids:
                print('Office {}/{} is not in API'.format(o.id, o.name))
                o.delete()

        del oids

        return {'username': response['username']}


    @fstamp
    def refresh_token(self, token, *args, **kwargs):
        ''' in-work
        '''
        params = self.refresh_token_params(token, *args, **kwargs)
        request = self.request(self.REFRESH_TOKEN_URL or self.ACCESS_TOKEN_URL,
                               data=params, headers=self.auth_headers(),
                               method='POST')
        return self.process_refresh_token_response(request, *args, **kwargs)

