from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage
from django.core.paginator import Paginator
from django.db.models import Q
from django.http.response import HttpResponse
from django.http.response import HttpResponseForbidden
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import FormView
from django_core.views.mixins.auth import LoginRequiredViewMixin

from .. import get_activity_model
from ..constants import Action
from ..constants import Source
from ..forms import ActivityActionForm
from ..http import ActivityResponse
from ..models import ActivityReply


Activity = get_activity_model()


class ActivityViewMixin(object):
    """View mixin for a single activity object."""

    activity = None
    activity_pk_url_kwarg = 'activity_id'

    def dispatch(self, *args, **kwargs):
        self.activity = self.get_activity(**kwargs)
        return super(ActivityViewMixin, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ActivityViewMixin, self).get_context_data(**kwargs)
        context['activity'] = self.activity
        context['activity_url'] = self.get_activity_url()
        return context

    def get_activity(self, **kwargs):
        if self.activity:
            return self.activity

        self.activity = Activity.objects.get_by_id_or_404(
            id=kwargs.get(self.activity_pk_url_kwarg)
        )

        if self.activity.is_public() or \
           self.activity.created_user == self.request.user:
            return self.activity

        # Check to ensure the user has permission to view the activity since the
        # activity is private.
        user = self.request.user

        if (not user.is_authenticated() or
            not self.activity.for_objs.filter(
                content_type=ContentType.objects.get_for_model(user),
                object_id=user.id
            ).exists()):
            raise PermissionDenied

        return self.activity

    def get_activity_url(self):
        """Gets the root activity url for the object the activity is about."""
        prefix = ''

        if self.activity.about and hasattr(self.activity.about,
                                           'get_activities_url'):
            return self.activity.about.get_activities_url()

        if hasattr(self.activity.about, 'get_absolute_url'):
            prefix = self.activity.about.get_absolute_url()

        return '{0}/activities'.format(prefix)


class ActivitySingleObjectViewMixin(ActivityViewMixin, SingleObjectMixin):
    """Mixin for when the activity represents what the page is about."""

    def dispatch(self, *args, **kwargs):
        self.object = self.get_object(**kwargs)
        return super(ActivitySingleObjectViewMixin, self).dispatch(*args,
                                                                   **kwargs)

    def get_object(self, **kwargs):
        return self.get_activity(**kwargs)


class ActivityReplyViewMixin(ActivityViewMixin):
    """View mixin for a activity reply."""

    activity_reply = None
    activity_reply_pk_url_kwarg = 'reply_id'

    def dispatch(self, *args, **kwargs):
        self.activity_reply = self.get_activity_reply(**kwargs)
        # I do this do the correct activity proxy model is used.
        self.activity_reply.activity = self.get_activity(**kwargs)
        return super(ActivityReplyViewMixin,
                     self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ActivityReplyViewMixin,
                        self).get_context_data(**kwargs)
        context['activity_reply'] = self.activity_reply
        return context

    def get_activity_reply(self, **kwargs):
        if self.activity_reply:
            return self.activity_reply

        self.activity_reply = ActivityReply.objects.get_by_id_or_404(
            id=kwargs.get(self.activity_reply_pk_url_kwarg),
            select_related=True
        )
        return self.activity_reply


class ActivityReplySingleObjectViewMixin(ActivityReplyViewMixin,
                                         SingleObjectMixin):
    """Mixin for when the activity reply represents what the page is about.
    """

    def dispatch(self, *args, **kwargs):
        self.object = self.get_object(**kwargs)
        return super(ActivityReplySingleObjectViewMixin,
                     self).dispatch(*args, **kwargs)

    def get_object(self, **kwargs):
        return self.get_activity_reply(**kwargs)


class ActivitiesViewMixin(object):
    """Activities view mixin that returns the activity_obj's paginator
    and current page the the authenticated user is able to see.

    Filtering:

    You can further filter the activities by passing the following query
    string params:

    * as: activity source.  Can be one of .contants.Source.
    * aa: activity action.  Can be one of .contants.Action.

    Note: This mixin requires the django_core.mixins.paging.PagingViewMixin
    to be called before this view is called.
    """
    activities_page_num = 1
    activities_page_size = 15
    activities_paginate_by = activities_page_size
    activities_page_kwarg = 'ap'
    activities_page_size_kwarg = 'aps'

    def dispatch(self, *args, **kwargs):

        if self.activities_page_size != self.activities_paginate_by:
            # Default to the paginate_by value if these two if different.
            self.activities_page_size = self.activities_paginate_by

        self.activities_page_num, self.activities_page_size = \
            self.get_activities_paging()
        self.activities_paginate_by = self.activities_page_size
        return super(ActivitiesViewMixin, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ActivitiesViewMixin,
                        self).get_context_data(**kwargs)

        activities = self.get_activities_queryset()

        paginator = Paginator(activities, self.activities_page_size)
        context['activities_paginator'] = paginator

        try:
            context['activities_page'] = \
                paginator.page(self.activities_page_num)
        except EmptyPage:
            context['activities_page'] = paginator.page(paginator.num_pages)

        about = self.get_activities_about_object()
        context['activities_about_object'] = about

        self.get_user_shared_objects(context=context)

        if 'activity_url' not in context:
            context['activity_url'] = self.get_activity_url()

        return context

    def get_user_shared_objects(self, context):
        """Gets the dict of object shares by content type so the user can know
        if they have already shared that object.
        """
        if not self.request.user.is_authenticated():
            # no updates to make for unauthenticated users
            return

        # get the list of objects this user has shares to
        user_share_filters = None

        about_objects_by_content_type_ids = {}

        # group the objects by content type
        for activity in context['activities_page'].object_list:
            content_type_id = activity.about_content_type_id
            about_id = activity.about_id

            if content_type_id not in about_objects_by_content_type_ids:
                about_objects_by_content_type_ids[content_type_id] = set([])

            about_objects_by_content_type_ids[content_type_id].add(about_id)

        # create the filters from the grouped objects content types
        for content_type_id, about_ids in about_objects_by_content_type_ids.items():
            queryset_filter_kwargs = {
                'about_content_type_id':content_type_id
            }

            about_ids = list(about_ids)

            if len(about_ids) == 1:
                queryset_filter_kwargs['about_id'] = about_ids[0]
            else:
                queryset_filter_kwargs['about_id__in'] = about_ids

            queryset_filter = Q(**queryset_filter_kwargs)

            if user_share_filters:
                user_share_filters |= queryset_filter
            else:
                user_share_filters = queryset_filter

        queryset_kwargs = {
            'action':Action.SHARED,
            'created_user': self.request.user
        }

        if user_share_filters:
            shared_objects = Activity.objects.filter(user_share_filters,
                                                     **queryset_kwargs)
        else:
            shared_objects = Activity.objects.filter(**queryset_kwargs)

        shared_objects = shared_objects.values_list(
            'about_content_type', 'about_id'
        )

        shares_by_content_type = {}
        for content_type_id, obj_id in shared_objects:

            if content_type_id not in shares_by_content_type:
                shares_by_content_type[content_type_id] = set([obj_id])
            else:
                shares_by_content_type[content_type_id].add(obj_id)

        context['user_shared_objects_by_content_type'] = shares_by_content_type

    def get_activities_common_queryset(self, queryset):
        """Common filters to apply to a queryset."""
        activity_kwargs = {}
        activity_source = Source.check(self.request.GET.get('as'))

        if activity_source:
            activity_kwargs['source'] = activity_source

        activity_action = Action.check(self.request.GET.get('aa'))

        if activity_action:
            activity_kwargs['action'] = activity_action

        prefetch_fields = self.get_activity_prefetch_related_fields()
        queryset = queryset.filter(**activity_kwargs)

        if prefetch_fields:
            return queryset.prefetch_related(*prefetch_fields)

        return queryset

    def get_activity_prefetch_related_fields(self):
        """Returns a list of the activity fields to prefetch."""
        return [
            'about',
            'about_content_type',
            'replies',
            'replies__created_user',
            'created_user'
        ]

    def get_activities_queryset(self):
        """Get's the queryset for the activities."""
        activities_about_object = self.get_activities_about_object()
        queryset = Activity.objects.get_about_object(
            about=activities_about_object
        ).order_by('-created_dttm')
        return self.get_activities_common_queryset(queryset=queryset)

    def get_activities_about_object(self):
        """Gets the object to get activities for. The default is to return
        self.object which will be set if using a DetailView.  Otherwise, the
        consuming View can override this method.

        This can be a single object or a list, tuple or set of objects.
        """
        if hasattr(self, 'object') and self.object is not None:
            return self.object

        return self.get_object()

    def get_activity_url(self):
        """Get the activity url for the activity object."""
        # TODO: Would be nice to try and optimize this so I don't have to query
        #       for the content type if possible.
        about_obj = self.get_activities_about_object()
        # content_type = ContentType.objects.get_for_model(about_obj)
        # return reverse('activities_view', args=[content_type.id, about_obj.id])

        prefix = ''

        if hasattr(about_obj, 'get_absolute_url'):
            prefix = about_obj.get_absolute_url()

        return '{0}/activities'.format(prefix)

    def get_activities_paging(self):
        """Gets the paging values passed through the query string params.

            * "np" for "activities page number" and
            * "nps" for "activities page size".

        :returns: tuple with the page being the first part and the page size
            being the second part.
        """
        orig_page_num = self.activities_page_num
        orig_page_size = self.activities_page_size

        try:

            page_num = int(self.request.GET.get(self.activities_page_kwarg))

            if page_num < 1:
                page_num = orig_page_num
        except:
            page_num = orig_page_num

        try:
            orig_page_size = self.activities_page_size
            page_size = int(self.request.GET.get(
                self.activities_page_size_kwarg)
            )

            if page_size < 1:
                page_size = orig_page_size
        except:
            page_size = orig_page_size

        return page_num, page_size


class ActivityCreatedUserRequiredViewMixin(LoginRequiredViewMixin):
    """View mixin for activity views that require the created user."""
    def dispatch(self, *args, **kwargs):

        if self.request.user != self.get_object(**kwargs).created_user:
            raise PermissionDenied

        return super(ActivityCreatedUserRequiredViewMixin,
                     self).dispatch(*args, **kwargs)


class UserActivitiesViewMixin(ActivitiesViewMixin):
    """Activities for the authenticated user."""

    def get_activities_about_object(self):
        return self.request.user


class ActivityFormView(FormView):
    """This is a form view that handles adding and displaying activities
    for an object.

    This must be called after after any subclass of
    activities.mixins.ActivitiesViewMixin so this mixin has access
    to the `activities_about_object` attribute.
    """
    form_class = ActivityActionForm

    def get_form_kwargs(self, **kwargs):
        form_kwargs = super(ActivityFormView, self).get_form_kwargs(**kwargs)
        form_kwargs['user'] = self.request.user
        form_kwargs['about'] = self.get_activities_about_object()
        return form_kwargs

    def get(self, request, *args, **kwargs):
        # TODO: do I need to make an additional check here to make sure this is
        #       an ajax get request for activities?
        if self.request.is_ajax():
            return render_to_response(
                'activities/snippets/activities.html',
                self.get_context_data(),
                context_instance=RequestContext(self.request)
            )

        return super(ActivityFormView, self).get(request=request,
                                                 *args,
                                                 **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ActivityFormView, self).get_context_data(**kwargs)

        if self.request.is_ajax():
            context['obj'] = self.get_activities_about_object()

        return context

    def form_valid(self, form):
        activity_or_activity_reply = form.save()

        if self.request.is_ajax():
            if activity_or_activity_reply is None:
                # no activity or activity reply found.  This is likely beacuse
                # it was a share or "repost" and was removed.
                return HttpResponse(status=204)

            return ActivityResponse(request=self.request,
                                    activity=activity_or_activity_reply)

        # TODO: Where do I redirect to if it's not an ajax request?
        # return ''  # safe_redirect(self.request.POST.get('next') or '/')
        return super(ActivityFormView, self).form_valid(form=form)

    def form_invalid(self, form):
        if self.request.is_ajax():
            return HttpResponseForbidden(content=form.errors)

        return super(ActivityFormView, self).form_invalid(form=form)
