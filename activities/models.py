from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import F
from django.db.models.deletion import SET_NULL
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.utils.translation import ugettext as _
from django_core.db.models.mixins.base import AbstractBaseModel
from django_core.db.models.mixins.generic import AbstractGenericObject
from django_core.db.models.mixins.urls import AbstractUrlLinkModelMixin

from .constants import Action
from .constants import Privacy
from .constants import Source
from .managers import ActivityForManager
from .managers import ActivityManager
from .managers import ActivityReplyManager


class AbstractActivity(AbstractBaseModel):
    """Abstract extensible model for Activities.

    Attributes:

    * about: object the activity is referring to.
    * about_id: id this object the activity pertains to.
    * about_content_type: the content type of the about object
    * text: the text of the activity.  This can include html. This is not
        required because you can construct the text based on the other object
        attributes.  For example, if I have an object ``car`` with a status of
        ``CREATED`` then I can construct the text as follows:

            ``Car object`` was ``created`` by ``created_user``
    * replies: list of replies to this activity
    * for_objs: list of docs this activity is for. For example,
        if a comment is made on a object "A" which has an object "B", then this
        list will include references to the::

            1. object "A"
            2. object "B"
            4. users who are sharing this object

    * source: the source of activity.  Can be one if constant.Source
        choices (i.e. 'USER' generated comment, 'SYSTEM' activity on an
        object, etc)
    * action: the action (verb) that describes what happend ('CREATED',
        'UPDATED', 'DELETED', 'COMMENTED', etc)
    * privacy: the privacy of the activity.  Can be either 'PUBLIC' or
        'PRIVATE'.
    * group: the activity group.  This represents a group of activities that
        may have happened at the same time or should be grouped for some reason.
        For example, uploading 100 images as once probably only needs one
        reference when listing out activities instead of listing 100 out
        individually.
    * reply_count: the denormalized number of replies to this activity
    """
    text = models.TextField(blank=True, null=True)
    about = GenericForeignKey(ct_field='about_content_type',
                              fk_field='about_id')
    about_content_type = models.ForeignKey(ContentType, null=True, blank=True)
    about_id = models.PositiveIntegerField(null=True, blank=True)
    reply_count = models.IntegerField(default=0)
    for_objs = models.ManyToManyField('ActivityFor',
                                      related_name='for_objs',
                                      blank=True)
    source = models.CharField(max_length=20, choices=Source.CHOICES)
    action = models.CharField(max_length=20, choices=Action.CHOICES)
    privacy = models.CharField(max_length=20, choices=Privacy.CHOICES,
                               default=Privacy.PRIVATE)
    group = models.ForeignKey('self', blank=True, null=True,
                              related_name='grouping',
                              on_delete=SET_NULL)
    objects = ActivityManager()

    class Meta:
        abstract = True

    def is_comment(self):
        """Boolean indicating if the activity type is a comment."""
        return self.action == Action.COMMENTED

    def is_activity(self):
        """Boolean indicating if the activity type is an activity."""
        return self.source == Source.SYSTEM

    def is_public(self):
        """Boolean indicating if the activity is public."""
        return self.privacy == Privacy.PUBLIC

    def add_reply(self, user, text, reply_to=None):
        """Adds a reply to a Activity

        :param user: the user the reply is from.
        :param text: the text for the reply.
        :param reply_to: is a reply to a specific reply.

        """
        reply = self.replies.create(created_user=user,
                                    last_modified_user=user,
                                    text=text,
                                    reply_to=reply_to,
                                    activity=self)
        # TODO: If the user isn't part of the for_objs they should be added
        #       because they are not part of the conversation?
        # self.activityfor_set.get_or_create_generic(content_object=user)
        return reply

    def get_shared_action_display_text(self):
        """Get the display text used for the "shared" action in case the system
        wants different working (i.e. "reposted" instead of "shared").
        """
        if hasattr(self.about, 'get_activity_shared_action_display_text'):
            return self.about.get_activity_shared_action_display_text()

        return Action.SHARED.lower()

    def get_action_html(self, force=False, **kwargs):
        """Gets the action text in the activity header.

        :param force: boolean indicating if the "about" object should be ignored
            when rendering this text.  This can be leveraged when things just
            want to be appended to the action html.  Force will get the original
            action html message.
        """
        if self.action not in (Action.ADDED, Action.CREATED, Action.SHARED,
                               Action.UPLOADED):
            # no activity text to return
            return ''

        if hasattr(self.about, 'get_activity_action_html') and force != True:
            return self.about.get_activity_action_html(self, **kwargs)

        object_name = self.about_content_type.model_class()._meta.verbose_name
        object_ref = object_name
        # these are common words that require "an" in the action text
        an_words = ['album', 'audio', 'image']
        a_or_an = 'a'

        if object_name.lower() in an_words:
            a_or_an = 'an'

        if hasattr(self.about, 'get_absolute_url'):
            object_ref = '<a href="{0}">{1}</a>'.format(
                self.about.get_absolute_url(),
                object_name
            )

        action_display = self.action.lower()

        # add any icon prefixes
        if self.action == Action.SHARED:
            action_display = '<i class="fa fa-retweet"></i> {0}'.format(
                self.get_shared_action_display_text()
            )

        return '{action} {a_or_an} {object_ref}'.format(
            action=action_display,
            a_or_an=a_or_an,
            object_ref=object_ref
        )

    def get_text(self):
        """Gets the text for an object.  If text is None, this will construct
        the text based on the activity attributes.
        """
        if self.text:
            return self.text

        action = Action.get_display(self.action) or self.action

        if self.action == Action.COMMENTED:
            template = '{created_user} {action} on the {object_name} {object}'
        else:
            template = '{created_user} {action} the {object_name} {object}'

        # TODO: need to differentiate system activity from user created
        #       activity.
        return template.format(
            created_user=self.created_user.username,
            action=action.lower(),
            object_name=self.about_content_type.model_class()._meta.verbose_name,
            object=self.about
        )

    def get_html(self, auth_user=None, **kwargs):
        """Does the same thing as ``get_text(...)`` but looks to see
        if the objects have the ``get_absolute_url`` method implemented.  If
        they do, then they will appear as links.  For example, if the user
        model implements the ``get_absolute_url`` the user's text will be
        hyperlinked to the user's absolute url.

        :param auth_user: the authenticated user if one is known.
        :param kwargs: the keyword args that will be passed to the "about"
            object specific function.
        """
        if self.text:
            return self.text

        # check to see if the about model has implemented a custom template
        activity_html_func_name = 'get_activity_{0}_html'.format(
            self.action.lower()
        )

        if hasattr(self.about, activity_html_func_name):
            # custom formatting function exists.  Use it.
            html_func = getattr(self.about, activity_html_func_name)
            return html_func(self, auth_user=auth_user, **kwargs)

        action = Action.get_display(self.action) or self.action

        created_user = self.created_user

        if hasattr(self.created_user, 'get_absolute_url_link'):
            created_user = self.created_user.get_absolute_url_link()
        elif hasattr(self.created_user, 'get_absolute_url'):
            created_user = '<a href="{0}">{1}</a>'.format(
                created_user.get_absolute_url(),
                created_user.username
            )
        else:
            created_user = self.created_user.username

        about = self.about

        if hasattr(self.about, 'get_absolute_url_link'):
            about = self.about.get_absolute_url_link()
        elif hasattr(self.about, 'get_absolute_url'):
            about = '<a href="{0}">{1}</a>'.format(about.get_absolute_url(),
                                                   about)

        if self.action == Action.COMMENTED:
            template = _('{created_user} {action} on the {object_name} '
                         '{object}.')
        else:
            template = _('{created_user} {action} the {object_name} {object}.')

        # TODO: need to differentiate system activity from user created
        #       activity.
        return template.format(
            created_user=created_user,
            action=action.lower(),
            object_name=self.about_content_type.model_class()._meta.verbose_name,
            object=about
        )

    def get_for_objects(self):
        """Gets the actual objects the activity is for."""
        return [obj.content_object
                for obj in self.for_objs.all().prefetch_related(
                                                            'content_object')]

    def get_reply_by_id(self, reply_id):
        """Gets the reply for a activity by it's id."""
        return self.replies.get(id=reply_id)

    def delete_reply(self, reply_id):
        """Delete an individual activity reply.

        :param activity_id: ID of the activity reply to delete

        """
        self.replies.filter(id=reply_id).delete()
        return True


class Activity(AbstractUrlLinkModelMixin, AbstractActivity):
    """Concrete model for activities."""

    objects = ActivityManager()

    class Meta:
        index_together = (
            ('about_id', 'about_content_type', 'created_dttm'),
            ('created_user', 'action', 'privacy', 'created_dttm')
        )

    def get_absolute_url(self):
        if self.about and hasattr(self.about, 'get_activities_url'):
            return '{0}/{1}'.format(self.about.get_activities_url(), self.id)

        return '/activities/{0}'.format(self.id)

    def get_edit_url(self):
        return '{0}/edit'.format(self.get_absolute_url())

    def get_delete_url(self):
        return '{0}/delete'.format(self.get_absolute_url())

    @classmethod
    def post_delete(cls, sender, instance, **kwargs):
        """Post delete fires after the object is deleted."""
        if (instance.action == Action.SHARED and
            instance.about and
            hasattr(instance.about, 'share_count')):
            # check to see if the share count has been denormalized on the
            # about object.  If so, increment the value.
            if instance.about.share_count > 0:
                share_count = F('share_count') - 1
            else:
                # can't have a negative share count
                share_count = 0

            type(instance.about).objects.filter(id=instance.about.id).update(
                share_count=share_count
            )

    @classmethod
    def post_save(cls, sender, instance, created, **kwargs):
        """Post save signal that fires after saved."""

        if (created and
            instance.action == Action.SHARED and
            instance.about and
            hasattr(instance.about, 'share_count')):
            # check to see if the share count has been denormalized on the
            # about object.  If so, increment the value.
            type(instance.about).objects.filter(id=instance.about.id).update(
                share_count=F('share_count') + 1
            )


post_save.connect(Activity.post_save, sender=Activity)
post_delete.connect(Activity.post_delete, sender=Activity)


class ActivityReply(AbstractUrlLinkModelMixin, AbstractBaseModel):
    """Represents a activity reply object.

    Attributes:

    * text: the text of the activity.  This can include html.
    * created_user: the person the activity was from.  This is the user who
            caused the activity to change.  This can be the same user as
            the activity is intended for (users can create activities
            for themselves)
    * reply_to: this is a reply to a reply and is a recursive reference.

    """
    text = models.TextField(max_length=500)
    activity = models.ForeignKey('Activity', related_name='replies')
    reply_to = models.ForeignKey('self', blank=True, null=True)
    objects = ActivityReplyManager()

    class Meta:
        index_together = (('activity', 'created_dttm'),)

    def get_absolute_url(self):
        return '{0}/replies/{1}'.format(self.activity.get_absolute_url(),
                                        self.id)

    def get_edit_url(self):
        return '{0}/edit'.format(self.get_absolute_url())

    def get_delete_url(self):
        return '{0}/delete'.format(self.get_absolute_url())

    @classmethod
    def post_save(cls, sender, instance, created, **kwargs):
        """Post save signal that fires after saved."""

        if created:
            Activity.objects.filter(id=instance.activity.id).update(
                reply_count=F('reply_count') + 1
            )

    @classmethod
    def post_delete(cls, sender, instance, **kwargs):
        """Post delete fires after the object is deleted."""
        if instance.activity and instance.activity.reply_count > 0:
            Activity.objects.filter(id=instance.activity.id).update(
                reply_count=F('reply_count') - 1
            )


post_save.connect(ActivityReply.post_save, sender=ActivityReply)
post_delete.connect(ActivityReply.post_delete, sender=ActivityReply)


class ActivityFor(AbstractGenericObject):
    """Defines the generic object a activity is for."""
    objects = ActivityForManager()

    class Meta:
        index_together = (('object_id', 'content_type'),)

    def __str__(self):
        return '{0} {1}'.format(self.content_type, self.object_id)
