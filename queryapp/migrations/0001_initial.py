# Generated by Django 3.0.5 on 2020-05-12 14:43

import datetime
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CookPlace',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100, verbose_name='Название места')),
                ('shop', models.CharField(choices=[('hot_shop', 'Горячий цех'), ('cold_shop', 'Холодный цех')], default='hot_shop', max_length=25, verbose_name='Цех готовки')),
            ],
            options={
                'verbose_name': 'Место приготовления',
                'verbose_name_plural': 'Места приготовления',
            },
        ),
        migrations.CreateModel(
            name='CookStep',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.IntegerField(default=99, verbose_name='Позиция шага (порядок)')),
                ('desc', models.TextField(max_length=5000, verbose_name='Описание шага')),
                ('duration', models.DurationField(verbose_name='Длительность шага')),
                ('multiply_time', models.BooleanField(default=False, verbose_name='Увеличение времени выполнения при увеличении числа порций (в пропорции)')),
                ('cookplace', models.ForeignKey(blank=True, on_delete=django.db.models.deletion.DO_NOTHING, to='queryapp.CookPlace', verbose_name='Место выполнения')),
            ],
            options={
                'verbose_name': 'Шаг приготовления',
                'verbose_name_plural': 'Шаги приготовления',
            },
        ),
        migrations.CreateModel(
            name='Dish',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100, verbose_name='Название блюда')),
                ('shop', models.CharField(choices=[('hot_shop', 'Горячий цех'), ('cold_shop', 'Холодный цех')], default='hot_shop', max_length=25, verbose_name='Цех готовки')),
            ],
            options={
                'verbose_name': 'Блюдо',
                'verbose_name_plural': 'Блюда',
            },
        ),
        migrations.CreateModel(
            name='DishCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100, verbose_name='Название категории')),
            ],
            options={
                'verbose_name': 'Категория блюд',
                'verbose_name_plural': 'Категории блюд',
            },
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('post_date', models.DateTimeField(auto_now_add=True, verbose_name='Время добавления')),
                ('finished', models.BooleanField(default=False, verbose_name='Готовность')),
                ('finished_at', models.DateTimeField(auto_now=True, verbose_name='Время завершения')),
            ],
            options={
                'verbose_name': 'Заказ',
                'verbose_name_plural': 'Заказы',
            },
        ),
        migrations.CreateModel(
            name='OrderPosition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField(default=1, verbose_name='Количество порций')),
                ('duration', models.DurationField(default=datetime.timedelta(0), verbose_name='Длительность приготовления')),
                ('finished', models.BooleanField(default=False, verbose_name='Готовность')),
                ('dish', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='queryapp.Dish', verbose_name='Соответствующее блюдо')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='queryapp.Order', verbose_name='Соответствующий заказ')),
            ],
            options={
                'verbose_name': 'Позиция внутри заказа',
                'verbose_name_plural': 'Позиции внутри заказа',
            },
        ),
        migrations.AddField(
            model_name='dish',
            name='category',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.DO_NOTHING, to='queryapp.DishCategory', verbose_name='Категория'),
        ),
        migrations.CreateModel(
            name='CookStepPosition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('finished', models.BooleanField(default=False, verbose_name='Готовность')),
                ('finished_at', models.DateTimeField(auto_now=True, verbose_name='Время завершения')),
                ('cookstep', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='queryapp.CookStep', verbose_name='Соответствующий шаг')),
                ('orderpos', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='queryapp.OrderPosition', verbose_name='Соответствующая позиция заказа')),
            ],
            options={
                'verbose_name': 'Позиция шага приготовления',
                'verbose_name_plural': 'Позиции шагов приготовления',
            },
        ),
        migrations.AddField(
            model_name='cookstep',
            name='dish',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='queryapp.Dish', verbose_name='Блюдо'),
        ),
        migrations.AddField(
            model_name='cookstep',
            name='previous_steps',
            field=models.ManyToManyField(blank=True, to='queryapp.CookStep', verbose_name='Непосредственно предшествующие шаги (на 1 уровень назад)'),
        ),
    ]
