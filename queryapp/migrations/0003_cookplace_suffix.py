# Generated by Django 3.0.5 on 2020-05-12 15:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('queryapp', '0002_cookplace_position'),
    ]

    operations = [
        migrations.AddField(
            model_name='cookplace',
            name='suffix',
            field=models.CharField(blank=True, max_length=150, verbose_name='Скрытый суффикс (опционально)'),
        ),
    ]