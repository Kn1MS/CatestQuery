from django.contrib import admin

from .models import *

# Register your models here.

admin.site.register(DishCategory)
admin.site.register(Dish)
admin.site.register(CookStep)
admin.site.register(Order)
admin.site.register(OrderPosition)
admin.site.register(CookStepPosition)
admin.site.register(CookPlace)