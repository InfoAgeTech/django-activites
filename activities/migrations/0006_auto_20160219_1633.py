# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-02-19 16:33
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('activities', '0005_auto_20160219_1618'),
    ]

    operations = [
        migrations.AlterIndexTogether(
            name='activityfor',
            index_together=set([('object_id', 'content_type')]),
        ),
    ]