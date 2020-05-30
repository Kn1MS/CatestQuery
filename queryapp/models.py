import datetime
from datetime import timedelta

from django.db import models
from django.utils import timezone

class DishCategory(models.Model):
	title = models.CharField(max_length=100, verbose_name="Название категории")

	class Meta:
		verbose_name = "Категория блюд"
		verbose_name_plural = "Категории блюд"

	def __str__(self):
		return self.title

class CookPlace(models.Model):
	SHOP_CHOICES = [
		("hot_shop", "Горячий цех"),
		("cold_shop", "Холодный цех")
	]
	title = models.CharField(max_length=100, verbose_name = "Название места")
	suffix = models.CharField(max_length=150, blank = True, verbose_name = "Скрытый суффикс (опционально)")
	shop = models.CharField(max_length=25, choices = SHOP_CHOICES, default = "hot_shop", verbose_name = "Цех готовки")
	position = models.IntegerField(default = 9, verbose_name = "Позиция на странице очереди")

	class Meta:
		verbose_name = "Место приготовления"
		verbose_name_plural = "Места приготовления"

	def __str__(self):
		return self.title + " " + self.suffix

class Dish(models.Model):
	SHOP_CHOICES = [
		("hot_shop", "Горячий цех"),
		("cold_shop", "Холодный цех")
	]
	title = models.CharField(max_length=100, verbose_name="Название блюда")
	category = models.ForeignKey(DishCategory, on_delete = models.DO_NOTHING, default = 1, verbose_name="Категория")
	shop = models.CharField(max_length=25, choices = SHOP_CHOICES, default = "hot_shop", verbose_name = "Цех готовки")
	cook_duration_max = models.DurationField(null=True, blank=True, verbose_name="Максимальная длительность приготовления одним поваром (обновлять на рабочей панели)")
	cook_duration_min = models.DurationField(null=True, blank=True, verbose_name="Минимальная длительность приготовления одним поваром (обновлять на рабочей панели)")

	class Meta:
		verbose_name = "Блюдо"
		verbose_name_plural = "Блюда"

	def __str__(self):
		return self.title

class CookStep(models.Model):
	position = models.IntegerField(default=99, verbose_name="Позиция шага (порядок)")
	desc = models.TextField(max_length=5000, verbose_name="Описание шага")
	duration = models.DurationField(verbose_name="Длительность шага")
	dish = models.ForeignKey(Dish, on_delete = models.CASCADE, verbose_name="Блюдо")
	cookplace = models.ForeignKey(CookPlace, verbose_name="Место выполнения", blank = True, on_delete = models.DO_NOTHING)
	multiply_time = models.BooleanField(default = False, verbose_name="Увеличение времени выполнения при увеличении числа порций (в пропорции)")
	previous_steps = models.ManyToManyField('self', symmetrical = False, blank = True, verbose_name="Непосредственно предшествующие шаги (на 1 уровень назад)")

	class Meta:
		verbose_name = "Шаг приготовления"
		verbose_name_plural = "Шаги приготовления"

	def __str__(self):
		info_str = ("| Блюдо: " + self.dish.title + " | Очередь: №" + str(self.position) + " | Длительность: " + str(self.duration) + " | Сокр. описание: " + self.desc[:100] + " |") 
		return info_str

class Order(models.Model):
	post_date = models.DateTimeField(auto_now_add = True, verbose_name="Время добавления")
	finished = models.BooleanField(default=False, verbose_name="Готовность")
	finished_at = models.DateTimeField(auto_now=True, verbose_name="Время завершения")
	cook_duration_hs = models.DurationField(null=True, blank=True, verbose_name="Предполагаемая длительность приготовления в горячем цеху (вычисляется автоматически)")
	cook_duration_cs = models.DurationField(null=True, blank=True, verbose_name="Предполагаемая длительность приготовления в холодном цеху (вычисляется автоматически)")
	assumed_finish = models.DateTimeField(null=True, blank=True, verbose_name="Предполагаемое завершение приготовления заказа")
	assumed_start_hs = models.DateTimeField(null=True, blank=True, verbose_name="Предполагаемое начало приготовления части заказа в горячем цехе")
	assumed_start_cs = models.DateTimeField(null=True, blank=True, verbose_name="Предполагаемое начало приготовления части заказа в холодном цехе")
	single_shop_flag = models.BooleanField(default = False, blank = True, verbose_name="Выполнение в одном цехе")
	delay = models.DurationField(default=timedelta(seconds=0), blank=True, verbose_name="Предполагаемая задержка до начала готовки")

	class Meta:
		verbose_name = "Заказ"
		verbose_name_plural = "Заказы"

	def __str__(self):
		return str("| ID: " + str(self.id) + " | Добавлен: " + str(self.post_date) + " | Завершён: " + str(self.finished)  
			+ " | Позиции: " + str(self.orderposition_set.all()) + " |")

class OrderPosition(models.Model):
	order = models.ForeignKey(Order, on_delete = models.CASCADE, verbose_name="Соответствующий заказ")
	dish = models.ForeignKey(Dish, on_delete = models.CASCADE, verbose_name="Соответствующее блюдо")
	quantity = models.IntegerField(default=1, verbose_name="Количество порций")
	duration = models.DurationField(default=timedelta(), verbose_name="Длительность приготовления")
	finished = models.BooleanField(default=False, verbose_name="Готовность")

	class Meta:
		verbose_name = "Позиция внутри заказа"
		verbose_name_plural = "Позиции внутри заказа"

	def __str__(self):
		info_str = ("| Заказ: " + str(self.order.id)+ " | Количество порций: " + str(self.quantity) 
			+ " | Блюдо: " + self.dish.title + " |" )
		return info_str

class CookStepPosition(models.Model):
	cookstep = models.ForeignKey(CookStep, on_delete = models.CASCADE, verbose_name="Соответствующий шаг")
	orderpos = models.ForeignKey(OrderPosition, on_delete = models.CASCADE, verbose_name="Соответствующая позиция заказа")
	finished = models.BooleanField(default = False, verbose_name="Готовность")
	finished_at	 = models.DateTimeField(auto_now = True, verbose_name="Время завершения")

	class Meta:
		verbose_name = "Позиция шага приготовления"
		verbose_name_plural = "Позиции шагов приготовления"

	def __str__(self):
		info_str = ("| ID позиции: " + str(self.orderpos.id) + " | ID шага: " + str(self.cookstep.id) + " |")
		return info_str