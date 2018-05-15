#!/usr/bin/env python
import os
import sys

if 'runserver' in sys.argv:
    ekeys = [k for k in os.environ]
    for k in ekeys:
        if k in ('TZ','PWD','PATH','DJANGO_SETTINGS_MODULE','RUN_MAIN','LANG','PYTHONIOENCODING','LANGUAGE','LC_ALL'):
            continue
        del os.environ[k]
        print('deleted {}'.format(k))

    print('done cleaning')

os.environ['PYTHONIOENCODING']='utf-8'
os.environ['LANG']='en_US.UTF-8'
os.environ['LANGUAGE']='en_US.UTF-8'
os.environ['LC_ALL']='en_US.UTF-8'
print('✂'*30)

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "drchrono.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError:
        # The above import may fail for some other reason. Ensure that the
        # issue is really that Django is missing to avoid masking other
        # exceptions on Python 2.
        try:
            import django
        except ImportError:
            raise ImportError(
                "Couldn't import Django. Are you sure it's installed and "
                "available on your PYTHONPATH environment variable? Did you "
                "forget to activate a virtual environment?"
            )
        raise
    execute_from_command_line(sys.argv)
