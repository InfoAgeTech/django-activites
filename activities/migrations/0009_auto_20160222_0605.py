# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-02-22 06:05
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('activities', '0008_activity_reply_count'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='activityreply',
            options={},
        ),
        migrations.AlterIndexTogether(
            name='activityreply',
            index_together=set([('activity', 'created_dttm')]),
        ),
    ]
