# -*- coding: utf-8 -*-
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django_tools.models import AbstractBaseModel
from mongo_notifications.constants import NotificationSource
from mongo_notifications.documents.embedded import NotificationReply


class NotificationReply(AbstractBaseModel):
    """Represents a notification reply object.
    
    Attributes:
    
    * text: the text of the notification.  This can include html.
    * created_id: the person the notification was from.  This is the user who
            caused the notification to change.  This can be the same user as the 
            notification is intended for (users can create notifications for 
            themselves)
    * reply_to_id: this is a reply to a reply and is the id of the reply.
      
    """
    text = models.TextField(max_length=500)
    # TODO: foreignKey or integer field (foreign key to "self")?
    reply_to_id = models.PositiveIntegerField()


class NotificationFor(AbstractBaseModel):
    """Defines the generic object a notification is related to.
    
    TODO: Should make this a mixin!
    """

    class Meta:
        db_table = u'notifications_for'

    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    for_object = generic.GenericForeignKey('content_type', 'object_id')


class Notification(AbstractBaseModel):
    """Notifications.
    
    Attributes: 
    
    * doc: reference object the notication is referring to.
    * doc_id: Document id this object pertains to. If the type is "GROUP" then 
      the doc_id relates to the group.
    * text: the text of the notification.  This can include html.
    * replies: list of replies to this notification
    * related_docs: list of docs this notification is related to.  For example,
        if a comment is made on a bill instance which has a group, then this
        list will include references to the::
            
            1. bill instance
            2. bill
            3. bill group (if one exists) 
            4. users who are sharing the bill
            
    * source: the source of notification.  Can be one if NotificationSource 
        choices (i.e. 'user' generated comment, 'activity' on a bill, etc)

    """

    text = models.CharField()
    content_type = models.ForeignKey(ContentType)
    about = generic.GenericForeignKey('content_type', 'about_id')
    about_id = models.PositiveIntegerField()
    replies = models.ForeignKey(NotificationReply)
    # TODO: This should be a generic foreign key? Could be related to a user or a
    # specific model
    related_objs = models.ForeignKey('NotificationFor')
#    related_docs = ListField(GenericReferenceField(),
#                             required=True,
#                             db_field='rd')
    source = models.CharField(choices=NotificationSource.CHOICES)

    class Meta:
        db_table = u'notifications'
        ordering = ['-created_dttm']
        indexes = [('related_docs', 'source', 'created_dttm')]

#    meta = {'collection': 'notifications',
#            'indexes': [('related_docs', 'source', 'created_dttm')],
#            'ordering': ['-created_dttm'],
#            'allow_inheritance': True,
#            'cascade': False
#            }

    @classmethod
    def add(cls, created_user, text, about, source, ensure_related_objs=None):
        """Adds a notification.
        
        :param created_user: the user document who created the notification.
        :param text: the text of the notification
        :param obj: the document this notification is for.
        :param source: the source of the notifications. Can be one of 
            NotificationSource values.
        :param ensure_related_objs: list of docs to ensure will receive the 
            notification.
        :return: if notification is successfully added this returns True.  
            Doesn't return entire object because the could potentially be a ton
            of notifications and I won't want to return all of them.
        
        """
        n = cls(text=text.strip(),
                about=about,
                created=created_user,
                created_id=created_user.id,
                last_modified=created_user,
                last_modified_id=created_user.id,
                source=source)

        related_objs = [about, created_user]

        if ensure_related_objs:
            for obj in ensure_related_objs:
                related_objs.append(obj)

        n.related_objs.add(related_objs)
        n.save()

        return n


    def add_reply(self, usr, text, reply_to_id=None):
        """
        Adds a reply to a Notification
        
        :param usr: the user the reply is from.
        :param reply_to_id: is a reply to a specific reply.
        
        """
        kwargs = {'text':text,
                  'created': usr,
                  'created_id': usr.id,
                  'last_modified_id':usr.id}

        if reply_to_id:
            kwargs['reply_to_id'] = reply_to_id

        return self.replies.create(**kwargs)


    def get_reply_by_id(self, reply_id):
        """Gets the reply for a notification by it's id."""
        for reply in self.replies:
            if reply.id == reply_id:
                return reply


    @classmethod
    def get_by_user(cls, usr, source=None, page=1, page_size=25,
                    select_related=False):
        """Gets notifications for a user.

        :param user: the user to get the notifications for
        :param source: the source of the notifications. Can be one of
            NotificationSource values.
        :return: tuple first part a boolean if there's more notification or not
            the second part the notifications.

        """
        return cls.get_by_obj(obj=usr,
                              source=source,
                              page=page,
                              page_size=page_size,
                              select_related=select_related)


    @classmethod
    def get_by_obj(cls, obj, source=None, page=1, page_size=25,
                   select_related=False):
        """Gets notifications for a specific object.
        
        :param obj: the object the notifications are for
        :param source: the source of the notification.
        
        """
        criteria = {'related_objs': obj}

        if source:
            criteria['source'] = source

        return cls._get_many(criteria,
                             page=page,
                             page_size=page_size,
                             select_related=select_related)


    def delete_reply(self, reply_id):
        """Delete an individual notification for a user.
        
        :param user_id: user to remove the notification for
        :param notification_id: ID of the notification to delete
        
        """
        self.replies.__class__.objects.get(id=reply_id).delete()
        return True
