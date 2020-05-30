from django.urls import path

from . import views

app_name = "queryapp"
urlpatterns = [
	path('', views.index, name="index"),
	path('login/', views.pagelogin, name="login"),
	path('logout/', views.pagelogout, name='logout'),
	path('workpanel/', views.workpanel, name="workpanel"),
	path('orders/', views.orders, name="orders"),
	path('hsqueue/', views.hsqueue, name="hsqueue"),
	path('csqueue/', views.csqueue, name="csqueue"),
	path('addorder/', views.addorder, name="addorder"),
]