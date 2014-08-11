NOTE: This is not stable yet and will likely change!  Please don't use in production until the 1.0 release.

[<img src="https://travis-ci.org/InfoAgeTech/django-notifications.png?branch=master">](http://travis-ci.org/InfoAgeTech/django-notifications)
[<img src="https://coveralls.io/repos/InfoAgeTech/django-notifications/badge.png">](https://coveralls.io/r/InfoAgeTech/django-notifications)

====================
django-notifications
====================
django-notifications is a generic python notifications module written for django.  You can create notifications about any object type and share that comment with any object type.

Intallation
===========
Download the source from Github and run::

    python setup.py install

Dependencies
============
* [django-generic](https://github.com/InfoAgeTech/django-generic)
* [django-core](https://github.com/InfoAgeTech/django-core)

Configuration
=============
Config steps:

1. Add to installed apps. django-notifications has two dependencies which are listed above. Both need to be added to the installed apps in your settings file.::

        INSTALLED_APPS += (
            ...
            'django_core',
            'django_generic',
            'django_notifications',
            ...
        )


By default, django-notifications comes with builtin views.  You can use them if you like or totally write your own.

To use the views here are a few configuration steps to follow:

1. Create the html file that will be used as the gateway between your application templates and django-notifications templates.  A simple template would look something like::
    
        # base_notifications.html
        {% extends request.base_template %}
    
        {% block content %}
          {% block notifications_content %}{% endblock %}
        {% endblock %}

2. Once you're created the base notifications html file, you need to link to it in your settings.  In your settings file add the following setting that points to your template you just created::

        NOTIFICATIONS_BASE_TEMPLATE = 'path/to/your/template/base_notifications.html'

3. Add the context processor in your settings that's used to retrieve your custom base template::

        TEMPLATE_CONTEXT_PROCESSORS = (
            ...
            'django_notifications.context_processors.template_name',
            ...
        )

4. Add the urls::

        urlpatterns = patterns('',
            ...
            url(r'^notifications', include('django_notifications.urls')),
            ...
        )

5. There are also default .less and .js files that will assist the notifications as well.  These are optional and the js requires jquery.  The files are located at::

        /static/django_notifications/js/notifications.js
        /static/django_notifications/less/notifications.less

Form Rendering
--------------
Different apps render forms differently. With that in mind, this app lets you define the location for a function in your settings that will be used to render your forms.

For example,  if I want to use the [django-bootstrap-form](https://github.com/tzangms/django-bootstrap-form) app to render forms, I would provide the following setting to the template tag form rendering function::

    NOTIFICATIONS_FORM_RENDERER = 'bootstrapform.templatetags.bootstrap.bootstrap'

Then all forms will render using the django-bootstrap-form library.  You can optionally provide the following strings that will render that form using table, paragraph or list tags::

    NOTIFICATIONS_FORM_RENDERER = 'as_p'     # render form using <p> tags
    NOTIFICATIONS_FORM_RENDERER = 'as_table' # render form using <table>
    NOTIFICATIONS_FORM_RENDERER = 'as_ul'    # render form using <ul>

This will default to rending the form to however the form's ``__str__`` method is defined.

Examples
========
Below are some basic examples on how to use django-notifications::

    >>> from django.contrib.auth import get_user_model
    >>> from django_notifications.models import Notification
    >>>
    >>> User = get_user_model()
    >>> user = User.objects.create_user(username='hello')
    >>>
    >>> # The object the notification is about
    >>> about_obj = User.objects.create_user(username='world')
    >>> n = Notification.objects.create(created_user=user,
    ...                                 text='Hello world',
    ...                                 about=about_obj,
    ...                                 source='COMMENT')
    >>> n.text
    'Hello world'
    >>> user_notifications = Notification.objects.get_for_user(user=user)
    >>> len(user_notifications)
    1
    >>> object_notifications = Notification.objects.get_for_object(obj=about_obj)
    >>> len(object_notifications)
    1

Extend the Model
================
If all this configuration still isn't to your liking, then you can simply extend the Notification model::

    # my_notification_app/models.py
    
    from django_notifications.models import AbstractNotification
    
    class MyNotification(AbstractNotification):
        """Your concrete implementation of the notification app."""
        # Do your stuff here

Custom Notification Rendering
=============================
When rendering the notifications, the ``get_html`` will check to see if the notification ``about`` object has implemented custom rendering of the notification itself.  In order for the custom rendering to occur, the ``about`` object model needs to implement the class as follows:

    def get_notification_created_html(self, notification, **kwargs):
        """The notification renderer for a created notification about this object."""
        # do rendering that returns html
        return rendered_html

Tests
=====
From the ``tests`` directory where the manage.py file is, run:

    python manage.py test