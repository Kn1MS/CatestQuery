# Generated by Django 3.0.5 on 2020-05-18 17:05

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('queryapp', '0006_auto_20200516_0026'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='delay',
            field=models.DurationField(blank=True, default=datetime.timedelta(0), verbose_name='Предполагаемая задержка до начала готовки'),
        ),
    ]
