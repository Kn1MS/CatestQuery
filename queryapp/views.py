from django.shortcuts import render, redirect
from django.template import loader
from django.http import HttpResponse, Http404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models.functions import Least

import datetime
from datetime import timedelta

from .models import *
from .forms import *
from .custom_functions import *

# Create your views here.

def index(request):
	template = loader.get_template('queryapp/index.html')
	context = {}
	return HttpResponse(template.render(context, request))

def pagelogin(request):
	template = loader.get_template('queryapp/login.html')
	if request.method == 'POST':
		username = request.POST['username']
		password = request.POST['password']
		user = authenticate(request, username=username, password=password)
		if user is not None:
			login(request, user)
			return redirect('queryapp:workpanel')
	context = {}
	return HttpResponse(template.render(context, request))

def pagelogout(request):
	if request.method == 'GET':
		raise Http404("Page not found")
	if request.method == 'POST':
		logout(request)
		return redirect('queryapp:index')

@login_required
def workpanel(request):
	template = loader.get_template('queryapp/workpanel.html')

	if request.method == 'POST':
		if 'updatedishes' in request.POST:
			dishes_list = Dish.objects.all()
			for dish in dishes_list:
				cooksteps = CookStep.objects.filter(dish=dish).order_by("position")
				final_position = 1
				max_duration = timedelta()
				table_steps_duration = timedelta()
				mt_steps_duration = timedelta()
				final_duration = timedelta()
				longest_path = 0
				for step in cooksteps:
					if step.position > final_position:
						final_position = step.position
				dish_paths = CalculatePaths(dish, final_position)
				for path in dish_paths:
					cur_duration = timedelta()
					for pos in path:
						step = CookStep.objects.get(dish=dish, position=pos)
						cur_duration += step.duration
					if max_duration < cur_duration:
						max_duration = cur_duration
						longest_path = dish_paths.index(path)
				final_duration = max_duration
				for pos in dish_paths[longest_path]:
					step = CookStep.objects.get(dish=dish, position=pos)
					if step.cookplace.title == "Производственный стол":
						table_steps_duration += step.duration
				for step in cooksteps:
					if step.cookplace.title == "Производственный стол":
						final_duration += step.duration
				final_duration -= table_steps_duration
				dish.cook_duration_max = final_duration
				print(dish.cook_duration_max)
				dish.cook_duration_min = max_duration
				dish.save()
			return redirect('queryapp:workpanel')

	context = {}
	return HttpResponse(template.render(context, request))

@login_required
def orders(request):
	active_orders_list = Order.objects.filter(finished = False).order_by('id')
	finished_orders_list = Order.objects.filter(finished = True).order_by('finished_at')
	orders_list = Order.objects.order_by('id')
	orderpositions_list = OrderPosition.objects.all()
	template = loader.get_template('queryapp/orders.html')
	context = {
		'active_orders_list': active_orders_list,
		'finished_orders_list': finished_orders_list,
		'orders_list': orders_list,
		'orderpositions_list': orderpositions_list,
	}
	return HttpResponse(template.render(context, request))

@login_required
def hsqueue(request):
	template = loader.get_template('queryapp/hsqueue.html')

	initial_moment = timezone.now()
	hsplaces = CookPlace.objects.filter(shop="hot_shop").order_by("position")
	finished_steps = CookStepPosition.objects.filter(finished=True).order_by("-finished_at")
	inprogress_steps = CookStepPosition.objects.none()
	orders_list = Order.objects.filter(finished=False).order_by("post_date")

	for order in orders_list:
		orderpos_list_hs = OrderPosition.objects.filter(order=order, finished = False, dish__shop="hot_shop").order_by("duration")
		orderpos_list_cs = OrderPosition.objects.filter(order=order, finished = False, dish__shop="cold_shop").order_by("duration")
		if orderpos_list_hs:
			order.cook_duration_hs = orderpos_list_hs[0].duration
		else:
			order.cook_duration_hs = timedelta(seconds=0)
		if orderpos_list_cs:
			order.cook_duration_cs = orderpos_list_cs[0].duration
		else:
			order.cook_duration_cs = timedelta(seconds=0)
		if order.cook_duration_hs == timedelta(seconds=0) or order.cook_duration_cs == timedelta(seconds=0):
			order.single_shop_flag = True

	queue_hs = []
	queue_cs = []
	orders_list_hs = Order.objects.filter(finished=False, cook_duration_hs__gt=timedelta(seconds=0)).order_by("post_date")
	orders_list_cs = Order.objects.filter(finished=False, cook_duration_cs__gt=timedelta(seconds=0)).order_by("post_date")

	for order in orders_list_hs:
		queue_hs.append(order.id)

	for order in orders_list_cs:
		queue_cs.append(order.id)

	for idx, order in enumerate(orders_list):
		assumed_finish_hs = initial_moment + order.cook_duration_hs
		assumed_finish_cs = initial_moment + order.cook_duration_cs
		if idx > 0:
			for i in range(idx):
				if orders_list[i].cook_duration_hs != timedelta(seconds = 0):
					assumed_finish_hs += orders_list[i].cook_duration_hs
				if orders_list[i].cook_duration_cs != timedelta(seconds = 0):
					assumed_finish_cs += orders_list[i].cook_duration_cs
		order.assumed_finish = max(assumed_finish_hs, assumed_finish_cs)
		order.assumed_start_hs = order.assumed_finish - order.cook_duration_hs
		order.assumed_start_cs = order.assumed_finish - order.cook_duration_cs
		# Проверяем, не является ли заказ вероятно первым в принципе (его не надо править в любом случае) и есть ли он в очереди горячего цеха
		if idx > 0:
			# Проверяем, не является ли заказ первым в очереди горячего цеха (его всё ещё не надо править)
			if order.id in queue_hs:
				if queue_hs.index(order.id) > 0:
					if order.single_shop_flag == True:
						# Если заказ выполняется лишь в одном цехе, делаем лишь одну проверку: сверяем начало выбранного заказа с концом предыдущего в очереди горячего цеха.
						prev_order_hs = Order.objects.get(id = queue_hs[queue_hs.index(order.id) - 1])
						if order.assumed_start_hs < prev_order_hs.assumed_finish:
							# Если начало меньше конца, то сдвигаем заказ вперёд и корректируем конец и начало
							order.assumed_finish = prev_order_hs.assumed_finish + order.cook_duration_hs
							order.assumed_start_hs = order.assumed_finish - order.cook_duration_hs
							order.assumed_start_cs = order.assumed_finish
					else:
						# Если заказ выполняется в обоих цехах, делаем две проверку: сверяем начало выбранного заказа с концом предыдущего в очереди горячего цеха и аналогично в холодно
						prev_order_hs = Order.objects.get(id = queue_hs[queue_hs.index(order.id) - 1])
						if queue_cs.index(order.id) > 0:
							# Если часть заказа в холодном цехе не является первой для очереди холодного цеха, то осуществляем полноценную проверку
							prev_order_cs = Order.objects.get(id = queue_cs[queue_cs.index(order.id) - 1])
							if order.assumed_start_hs < prev_order_hs.assumed_finish:
								assumed_finish_hs = prev_order_hs.assumed_finish + order.cook_duration_hs
							else:
								assumed_finish_hs = order.assumed_finish
							if order.assumed_start_cs < prev_order_cs.assumed_finish:
								assumed_finish_cs = prev_order_cs.assumed_finish + order.cook_duration_cs
							else:
								assumed_finish_cs = order.assumed_finish
							order.assumed_finish = max(assumed_finish_hs, assumed_finish_cs)
							order.assumed_start_hs = order.assumed_finish - order.cook_duration_hs
							order.assumed_start_cs = order.assumed_finish - order.cook_duration_cs
						else:
							# Иначе выполняем проверку как для заказа, выполняемого в одном из цехов, но корректируем время для обоих
							if order.assumed_start_hs < prev_order_hs.assumed_finish:
								assumed_finish_hs = prev_order_hs.assumed_finish + order.cook_duration_hs
								assumed_finish_cs = order.assumed_finish + order.cook_duration_cs
								order.assumed_finish = max(assumed_finish_hs, assumed_finish_cs)
								order.assumed_start_hs = order.assumed_finish - order.cook_duration_hs
								order.assumed_start_cs = order.assumed_finish - order.cook_duration_cs
			elif order.id in queue_cs:
				# Отдельно фиксим шаги, находящиеся только в холодном цехе, чтобы можно было правильно сдвигать шаги, находящиеся в обоих одновременно
				if queue_cs.index(order.id) > 0:
					prev_order_cs = Order.objects.get(id = queue_cs[queue_cs.index(order.id) - 1])
					if order.assumed_start_cs < prev_order_cs.assumed_finish:
						assumed_finish_cs = prev_order_cs.assumed_finish + order.cook_duration_cs
						assumed_finish_hs = order.assumed_finish
						order.assumed_finish = max(assumed_finish_hs, assumed_finish_cs)
						order.assumed_start_hs = order.assumed_finish - order.cook_duration_hs
						order.assumed_start_cs = order.assumed_finish - order.cook_duration_cs
		order.save()

	final_queue, queue_hs, queue_cs = CreateThreeQueues()
	queue_gaps_hs = GetQueueGaps(initial_moment, orders_list_hs, queue_hs, "hs")
	queue_gaps_cs = GetQueueGaps(initial_moment, orders_list_cs, queue_cs, "cs")

	optimized_flag = False
	# Оптимизируем до тех пор, пока не остаётся заказов, которые можно сдвинуть в свободные участки
	while optimized_flag == False:
		optimized_flag = True
		order_moved = False
		for idx, order_id in enumerate(final_queue):
			if order_moved == True:
				final_queue, queue_hs, queue_cs = CreateThreeQueues()
				orders_list_hs = Order.objects.filter(finished=False, cook_duration_hs__gt=timedelta(seconds=0)).order_by('assumed_start_hs')
				orders_list_cs = Order.objects.filter(finished=False, cook_duration_cs__gt=timedelta(seconds=0)).order_by('assumed_start_cs')
				queue_gaps_hs = GetQueueGaps(initial_moment, orders_list_hs, queue_hs, "hs")
				queue_gaps_cs = GetQueueGaps(initial_moment, orders_list_cs, queue_cs, "cs")
				break
			else:
				order = Order.objects.get(id = order_id)
				if order.single_shop_flag == True:
					if order.cook_duration_hs > timedelta(seconds=0):
						# Заказ находится целиком в очереди горячего цеха
						order_index = final_queue.index(order.id)
						order_index_hs = queue_hs.index(order.id)
						for i in range(order_index_hs):
							if queue_gaps_hs[i] > order.cook_duration_hs:
								# Нашли шаг, который можно сдвинуть. Очередь не оптимизирована (флаг на "Ложь")
								optimized_flag = False
								if i == 0:
									order.assumed_start_hs = initial_moment
									order.assumed_finish = initial_moment + order.cook_duration_hs
									order.assumed_start_cs = order.assumed_finish
								else:
									prev_order = Order.objects.get(id=queue_hs[i-1])
									order.assumed_start_hs = prev_order.assumed_finish
									order.assumed_finish = order.assumed_start_hs + order.cook_duration_hs
									order.assumed_start_cs = order.assumed_finish
								order.save()
								queue_hs.remove(order.id)
								queue_hs.insert(i, order.id)
								order_moved = True
								# Подправляем старты и финиши всех шагов после сдвинутого
								for i in range(order_index, len(final_queue)):
									fix_order = Order.objects.get(id = final_queue[i])
									# Если заказ целиком в одном цехе, то сверим с предыдущим шагом в очереди горячего цеха
									if fix_order.single_shop_flag == True:
										if fix_order.cook_duration_hs > timedelta(seconds=0):
											prev_order = Order.objects.get(id=queue_hs[queue_hs.index(fix_order.id)-1])
											if fix_order.assumed_start_hs > prev_order.assumed_finish:
												fix_order.assumed_start_hs = prev_order.assumed_finish
												fix_order.assumed_finish = fix_order.assumed_start_hs + fix_order.cook_duration_hs
												fix_order.assumed_start_cs = fix_order.assumed_finish
												fix_order.save()
										elif fix_order.cook_duration_cs > timedelta(seconds=0):
											prev_order = Order.objects.get(id=queue_cs[queue_cs.index(fix_order.id)-1])
											if fix_order.assumed_start_cs > prev_order.assumed_finish:
												fix_order.assumed_start_cs = prev_order.assumed_finish
												fix_order.assumed_finish = fix_order.assumed_start_cs + fix_order.cook_duration_cs
												fix_order.assumed_start_hs = fix_order.assumed_finish
												fix_order.save()
									else:
										# Если заказ в обоих цехах, то сверим части обеих цехов с их предшественниками по цеху
										# Затем выставим наибольший финал и подгоним старты
										prev_order_hs = Order.objects.get(id=queue_hs[queue_hs.index(fix_order.id)-1])
										prev_order_cs = Order.objects.get(id=queue_cs[queue_hs.index(fix_order.id)-1])
										if fix_order.assumed_start_hs > prev_order_hs.assumed_finish:
											fix_order.assumed_start_hs = prev_order_hs.assumed_finish
											assumed_finish_hs = fix_order.assumed_start_hs + fix_order.cook_duration_hs
										else:
											assumed_finish_hs = fix_order.assumed_start_hs + fix_order.cook_duration_hs
										if fix_order.assumed_start_cs > prev_order_cs.assumed_finish:
											fix_order.assumed_start_cs = prev_order_cs.assumed_finish
											assumed_finish_cs = fix_order.assumed_start_cs + fix_order.cook_duration_cs
										else:
											assumed_finish_cs = fix_order.assumed_start_cs + fix_order.cook_duration_cs
										fix_order.assumed_finish = max(assumed_finish_hs, assumed_finish_cs)
										fix_order.assumed_start_hs = fix_order.assumed_finish - fix_order.cook_duration_hs
										fix_order.assumed_start_cs = fix_order.assumed_finish - fix_order.cook_duration_cs
										fix_order.save()
								break
					elif order.cook_duration_cs > timedelta(seconds=0):
						# Заказ находится целиком в очереди холодного цеха
						order_index = final_queue.index(order.id)
						order_index_cs = queue_cs.index(order.id)
						for i in range(order_index_cs):
							if queue_gaps_cs[i] > order.cook_duration_cs:
								# Нашли шаг, который можно сдвинуть. Очередь не оптимизирована (флаг на "Ложь")
								optimized_flag = False
								if i == 0:
									order.assumed_start_cs = initial_moment
									order.assumed_finish = initial_moment + order.cook_duration_cs
									order.assumed_start_hs = order.assumed_finish
								else:
									prev_order = Order.objects.get(id=queue_cs[i-1])
									order.assumed_start_cs = prev_order.assumed_finish
									order.assumed_finish = order.assumed_start_cs + order.cook_duration_cs
									order.assumed_start_hs = order.assumed_finish
								order.save()
								queue_cs.remove(order.id)
								queue_cs.insert(i, order.id)
								order_moved = True
								# Подправляем старты и финиши всех шагов после сдвинутого
								for i in range(order_index, len(final_queue)):
									fix_order = Order.objects.get(id = final_queue[i])
									# Если заказ целиком в одном цехе, то сверим с предыдущим шагом в очереди горячего цеха
									if fix_order.single_shop_flag == True:
										if fix_order.cook_duration_hs > timedelta(seconds=0):
											prev_order = Order.objects.get(id=queue_hs[queue_hs.index(fix_order.id)-1])
											if fix_order.assumed_start_hs > prev_order.assumed_finish:
												fix_order.assumed_start_hs = prev_order.assumed_finish
												fix_order.assumed_finish = fix_order.assumed_start_hs + fix_order.cook_duration_hs
												fix_order.assumed_start_cs = fix_order.assumed_finish
												fix_order.save()
										elif fix_order.cook_duration_cs > timedelta(seconds=0):
											prev_order = Order.objects.get(id=queue_cs[queue_cs.index(fix_order.id)-1])
											if fix_order.assumed_start_cs > prev_order.assumed_finish:
												fix_order.assumed_start_cs = prev_order.assumed_finish
												fix_order.assumed_finish = fix_order.assumed_start_cs + fix_order.cook_duration_cs
												fix_order.assumed_start_hs = fix_order.assumed_finish
												fix_order.save()
									else:
										# Если заказ в обоих цехах, то сверим части обеих цехов с их предшественниками по цеху
										# Затем выставим наибольший финал и подгоним старты
										prev_order_hs = Order.objects.get(id=queue_hs[queue_hs.index(fix_order.id)-1])
										prev_order_cs = Order.objects.get(id=queue_cs[queue_cs.index(fix_order.id)-1])
										if fix_order.assumed_start_hs > prev_order_hs.assumed_finish:
											fix_order.assumed_start_hs = prev_order_hs.assumed_finish
											assumed_finish_hs = fix_order.assumed_start_hs + fix_order.cook_duration_hs
										else:
											assumed_finish_hs = fix_order.assumed_start_hs + fix_order.cook_duration_hs
										if fix_order.assumed_start_cs > prev_order_cs.assumed_finish:
											fix_order.assumed_start_cs = prev_order_cs.assumed_finish
											assumed_finish_cs = fix_order.assumed_start_cs + fix_order.cook_duration_cs
										else:
											assumed_finish_cs = fix_order.assumed_start_cs + fix_order.cook_duration_cs
										fix_order.assumed_finish = max(assumed_finish_hs, assumed_finish_cs)
										fix_order.assumed_start_hs = fix_order.assumed_finish - fix_order.cook_duration_hs
										fix_order.assumed_start_cs = fix_order.assumed_finish - fix_order.cook_duration_cs
										fix_order.save()
								break
	final_queue, queue_hs, queue_cs = CreateThreeQueues()
	orders_list_hs = Order.objects.filter(finished=False, cook_duration_hs__gt=timedelta(seconds=0)).order_by('assumed_start_hs')
	orders_list_cs = Order.objects.filter(finished=False, cook_duration_cs__gt=timedelta(seconds=0)).order_by('assumed_start_cs')
	queue_gaps_hs = GetQueueGaps(initial_moment, orders_list_hs, queue_hs, "hs")
	queue_gaps_cs = GetQueueGaps(initial_moment, orders_list_cs, queue_cs, "cs")

	optimized_flag = False
	while optimized_flag == False:
		optimized_flag = True
		order_moved = False
		for idx, order in enumerate(final_queue):
			if order_moved == True:
				final_queue, queue_hs, queue_cs = CreateThreeQueues()
				orders_list_hs = Order.objects.filter(finished=False, cook_duration_hs__gt=timedelta(seconds=0)).order_by('assumed_start_hs')
				orders_list_cs = Order.objects.filter(finished=False, cook_duration_cs__gt=timedelta(seconds=0)).order_by('assumed_start_cs')
				queue_gaps_hs = GetQueueGaps(initial_moment, orders_list_hs, queue_hs, "hs")
				queue_gaps_cs = GetQueueGaps(initial_moment, orders_list_cs, queue_cs, "cs")
				break
			else:
				for i in range(len(final_queue)):
					fix_order = Order.objects.get(id = final_queue[i])
					# Если заказ целиком в одном цехе, то сверим с предыдущим шагом в очереди горячего цеха
					if fix_order.single_shop_flag == True:
						if fix_order.cook_duration_hs > timedelta(seconds=0):
							prev_order = Order.objects.get(id=queue_hs[queue_hs.index(fix_order.id)-1])
							if fix_order.assumed_start_hs > prev_order.assumed_finish:
								order_moved = True
								optimized_flag = False
								fix_order.assumed_start_hs = prev_order.assumed_finish
								fix_order.assumed_finish = fix_order.assumed_start_hs + fix_order.cook_duration_hs
								fix_order.assumed_start_cs = fix_order.assumed_finish
								fix_order.save()
						elif fix_order.cook_duration_cs > timedelta(seconds=0):
							prev_order = Order.objects.get(id=queue_cs[queue_cs.index(fix_order.id)-1])
							if fix_order.assumed_start_cs > prev_order.assumed_finish:
								order_moved = True
								optimized_flag = False
								fix_order.assumed_start_cs = prev_order.assumed_finish
								fix_order.assumed_finish = fix_order.assumed_start_cs + fix_order.cook_duration_cs
								fix_order.assumed_start_hs = fix_order.assumed_finish
								fix_order.save()
					else:
						# Если заказ в обоих цехах, то сверим части обеих цехов с их предшественниками по цеху
						# Затем выставим наибольший финал и подгоним старты
						prev_order_hs = Order.objects.get(id=queue_hs[queue_hs.index(fix_order.id)-1])
						prev_order_cs = Order.objects.get(id=queue_cs[queue_cs.index(fix_order.id)-1])
						if fix_order.assumed_start_hs > prev_order_hs.assumed_finish:
							fix_order.assumed_start_hs = prev_order_hs.assumed_finish
							assumed_finish_hs = fix_order.assumed_start_hs + fix_order.cook_duration_hs
						else:
							assumed_finish_hs = fix_order.assumed_start_hs + fix_order.cook_duration_hs
						if fix_order.assumed_start_cs > prev_order_cs.assumed_finish:
							fix_order.assumed_start_cs = prev_order_cs.assumed_finish
							assumed_finish_cs = fix_order.assumed_start_cs + fix_order.cook_duration_cs
						else:
							assumed_finish_cs = fix_order.assumed_start_cs + fix_order.cook_duration_cs
						old_finish = fix_order.assumed_finish
						fix_order.assumed_finish = max(assumed_finish_hs, assumed_finish_cs)
						if old_finish != fix_order.assumed_finish:
							order_moved = True
							optimized_flag = False
						fix_order.assumed_start_hs = fix_order.assumed_finish - fix_order.cook_duration_hs
						fix_order.assumed_start_cs = fix_order.assumed_finish - fix_order.cook_duration_cs
						fix_order.save()
	orders_list_hs = Order.objects.filter(finished=False, cook_duration_hs__gt=timedelta(seconds=0)).order_by('assumed_start_hs')
	orders_list_cs = Order.objects.filter(finished=False, cook_duration_cs__gt=timedelta(seconds=0)).order_by('assumed_start_cs')

	for order in orders_list_hs:
		order.delay = order.assumed_start_hs - initial_moment
		order.save()
		orderpos_list = OrderPosition.objects.filter(order = order, finished = False, dish__shop = "hot_shop").order_by("duration")
		for orderpos in orderpos_list:
			unfinished_steps = CookStepPosition.objects.filter(orderpos = orderpos, finished = False).order_by("cookstep__position")
			for step in unfinished_steps:
				count = 0
				for prev_step in CookStepPosition.objects.filter(orderpos = step.orderpos, cookstep__in = step.cookstep.previous_steps.all()):
					if prev_step.finished == True:
						count += 1
				if count == step.cookstep.previous_steps.all().count():
					inprogress_steps = inprogress_steps.union(CookStepPosition.objects.filter(cookstep = step.cookstep, orderpos = step.orderpos))

	if request.method == 'POST':
		if request.POST.get("ready", ""):
			step_id = request.POST.get("ready", "")
			step = CookStepPosition.objects.get(id=step_id)
			step.finished = True
			step.save()
			return redirect('queryapp:hsqueue')
		if request.POST.get("return", ""):
			step_id = request.POST.get("return", "")
			step = CookStepPosition.objects.get(id=step_id)
			step.finished = False
			step.save()
			return redirect('queryapp:hsqueue')

	context = {
		'hsplaces': hsplaces,
		'finished_steps': finished_steps,
		'inprogress_steps': inprogress_steps,
		'zero_duration': timedelta(seconds=0),
	}
	return HttpResponse(template.render(context, request))

@login_required
def csqueue(request):
	template = loader.get_template('queryapp/csqueue.html')

	initial_moment = timezone.now()
	csplaces = CookPlace.objects.filter(shop="cold_shop").order_by("position")
	finished_steps = CookStepPosition.objects.filter(finished = True).order_by("-finished_at")
	inprogress_steps = CookStepPosition.objects.none()
	orders_list = Order.objects.filter(finished = False).order_by("post_date")

	for order in orders_list:
		orderpos_list_hs = OrderPosition.objects.filter(order=order, finished = False, dish__shop="hot_shop").order_by("duration")
		orderpos_list_cs = OrderPosition.objects.filter(order=order, finished = False, dish__shop="cold_shop").order_by("duration")
		if orderpos_list_hs:
			order.cook_duration_hs = orderpos_list_hs[0].duration
		else:
			order.cook_duration_hs = timedelta(seconds=0)
		if orderpos_list_cs:
			order.cook_duration_cs = orderpos_list_cs[0].duration
		else:
			order.cook_duration_cs = timedelta(seconds=0)
		if order.cook_duration_hs == timedelta(seconds=0) or order.cook_duration_cs == timedelta(seconds=0):
			order.single_shop_flag = True

	queue_hs = []
	queue_cs = []
	orders_list_hs = Order.objects.filter(finished=False, cook_duration_hs__gt=timedelta(seconds=0)).order_by("post_date")
	orders_list_cs = Order.objects.filter(finished=False, cook_duration_cs__gt=timedelta(seconds=0)).order_by("post_date")

	for order in orders_list_hs:
		queue_hs.append(order.id)

	for order in orders_list_cs:
		queue_cs.append(order.id)

	for idx, order in enumerate(orders_list):
		assumed_finish_hs = initial_moment + order.cook_duration_hs
		assumed_finish_cs = initial_moment + order.cook_duration_cs
		if idx > 0:
			for i in range(idx):
				if orders_list[i].cook_duration_hs != timedelta(seconds = 0):
					assumed_finish_hs += orders_list[i].cook_duration_hs
				if orders_list[i].cook_duration_cs != timedelta(seconds = 0):
					assumed_finish_cs += orders_list[i].cook_duration_cs
		order.assumed_finish = max(assumed_finish_hs, assumed_finish_cs)
		order.assumed_start_hs = order.assumed_finish - order.cook_duration_hs
		order.assumed_start_cs = order.assumed_finish - order.cook_duration_cs
		# Проверяем, не является ли заказ вероятно первым в принципе (его не надо править в любом случае) и есть ли он в очереди горячего цеха
		if idx > 0:
			# Проверяем, не является ли заказ первым в очереди горячего цеха (его всё ещё не надо править)
			if order.id in queue_hs:
				if queue_hs.index(order.id) > 0:
					if order.single_shop_flag == True:
						# Если заказ выполняется лишь в одном цехе, делаем лишь одну проверку: сверяем начало выбранного заказа с концом предыдущего в очереди горячего цеха.
						prev_order_hs = Order.objects.get(id = queue_hs[queue_hs.index(order.id) - 1])
						if order.assumed_start_hs < prev_order_hs.assumed_finish:
							# Если начало меньше конца, то сдвигаем заказ вперёд и корректируем конец и начало
							order.assumed_finish = prev_order_hs.assumed_finish + order.cook_duration_hs
							order.assumed_start_hs = order.assumed_finish - order.cook_duration_hs
							order.assumed_start_cs = order.assumed_finish
					else:
						# Если заказ выполняется в обоих цехах, делаем две проверку: сверяем начало выбранного заказа с концом предыдущего в очереди горячего цеха и аналогично в холодно
						prev_order_hs = Order.objects.get(id = queue_hs[queue_hs.index(order.id) - 1])
						if queue_cs.index(order.id) > 0:
							# Если часть заказа в холодном цехе не является первой для очереди холодного цеха, то осуществляем полноценную проверку
							prev_order_cs = Order.objects.get(id = queue_cs[queue_cs.index(order.id) - 1])
							if order.assumed_start_hs < prev_order_hs.assumed_finish:
								assumed_finish_hs = prev_order_hs.assumed_finish + order.cook_duration_hs
							else:
								assumed_finish_hs = order.assumed_finish
							if order.assumed_start_cs < prev_order_cs.assumed_finish:
								assumed_finish_cs = prev_order_cs.assumed_finish + order.cook_duration_cs
							else:
								assumed_finish_cs = order.assumed_finish
							order.assumed_finish = max(assumed_finish_hs, assumed_finish_cs)
							order.assumed_start_hs = order.assumed_finish - order.cook_duration_hs
							order.assumed_start_cs = order.assumed_finish - order.cook_duration_cs
						else:
							# Иначе выполняем проверку как для заказа, выполняемого в одном из цехов, но корректируем время для обоих
							if order.assumed_start_hs < prev_order_hs.assumed_finish:
								assumed_finish_hs = prev_order_hs.assumed_finish + order.cook_duration_hs
								assumed_finish_cs = order.assumed_finish + order.cook_duration_cs
								order.assumed_finish = max(assumed_finish_hs, assumed_finish_cs)
								order.assumed_start_hs = order.assumed_finish - order.cook_duration_hs
								order.assumed_start_cs = order.assumed_finish - order.cook_duration_cs
			elif order.id in queue_cs:
				# Отдельно фиксим шаги, находящиеся только в холодном цехе, чтобы можно было правильно сдвигать шаги, находящиеся в обоих одновременно
				if queue_cs.index(order.id) > 0:
					prev_order_cs = Order.objects.get(id = queue_cs[queue_cs.index(order.id) - 1])
					if order.assumed_start_cs < prev_order_cs.assumed_finish:
						assumed_finish_cs = prev_order_cs.assumed_finish + order.cook_duration_cs
						assumed_finish_hs = order.assumed_finish
						order.assumed_finish = max(assumed_finish_hs, assumed_finish_cs)
						order.assumed_start_hs = order.assumed_finish - order.cook_duration_hs
						order.assumed_start_cs = order.assumed_finish - order.cook_duration_cs
		order.save()

	final_queue, queue_hs, queue_cs = CreateThreeQueues()
	queue_gaps_hs = GetQueueGaps(initial_moment, orders_list_hs, queue_hs, "hs")
	queue_gaps_cs = GetQueueGaps(initial_moment, orders_list_cs, queue_cs, "cs")

	optimized_flag = False
	# Оптимизируем до тех пор, пока не остаётся заказов, которые можно сдвинуть в свободные участки
	while optimized_flag == False:
		optimized_flag = True
		order_moved = False
		for idx, order_id in enumerate(final_queue):
			if order_moved == True:
				final_queue, queue_hs, queue_cs = CreateThreeQueues()
				orders_list_hs = Order.objects.filter(finished=False, cook_duration_hs__gt=timedelta(seconds=0)).order_by('assumed_start_hs')
				orders_list_cs = Order.objects.filter(finished=False, cook_duration_cs__gt=timedelta(seconds=0)).order_by('assumed_start_cs')
				queue_gaps_hs = GetQueueGaps(initial_moment, orders_list_hs, queue_hs, "hs")
				queue_gaps_cs = GetQueueGaps(initial_moment, orders_list_cs, queue_cs, "cs")
				break
			else:
				order = Order.objects.get(id = order_id)
				if order.single_shop_flag == True:
					if order.cook_duration_hs > timedelta(seconds=0):
						# Заказ находится целиком в очереди горячего цеха
						order_index = final_queue.index(order.id)
						order_index_hs = queue_hs.index(order.id)
						for i in range(order_index_hs):
							if queue_gaps_hs[i] > order.cook_duration_hs:
								# Нашли шаг, который можно сдвинуть. Очередь не оптимизирована (флаг на "Ложь")
								optimized_flag = False
								if i == 0:
									order.assumed_start_hs = initial_moment
									order.assumed_finish = initial_moment + order.cook_duration_hs
									order.assumed_start_cs = order.assumed_finish
								else:
									prev_order = Order.objects.get(id=queue_hs[i-1])
									order.assumed_start_hs = prev_order.assumed_finish
									order.assumed_finish = order.assumed_start_hs + order.cook_duration_hs
									order.assumed_start_cs = order.assumed_finish
								order.save()
								queue_hs.remove(order.id)
								queue_hs.insert(i, order.id)
								order_moved = True
								# Подправляем старты и финиши всех шагов после сдвинутого
								for i in range(order_index, len(final_queue)):
									fix_order = Order.objects.get(id = final_queue[i])
									# Если заказ целиком в одном цехе, то сверим с предыдущим шагом в очереди горячего цеха
									if fix_order.single_shop_flag == True:
										if fix_order.cook_duration_hs > timedelta(seconds=0):
											prev_order = Order.objects.get(id=queue_hs[queue_hs.index(fix_order.id)-1])
											if fix_order.assumed_start_hs > prev_order.assumed_finish:
												fix_order.assumed_start_hs = prev_order.assumed_finish
												fix_order.assumed_finish = fix_order.assumed_start_hs + fix_order.cook_duration_hs
												fix_order.assumed_start_cs = fix_order.assumed_finish
												fix_order.save()
										elif fix_order.cook_duration_cs > timedelta(seconds=0):
											prev_order = Order.objects.get(id=queue_cs[queue_cs.index(fix_order.id)-1])
											if fix_order.assumed_start_cs > prev_order.assumed_finish:
												fix_order.assumed_start_cs = prev_order.assumed_finish
												fix_order.assumed_finish = fix_order.assumed_start_cs + fix_order.cook_duration_cs
												fix_order.assumed_start_hs = fix_order.assumed_finish
												fix_order.save()
									else:
										# Если заказ в обоих цехах, то сверим части обеих цехов с их предшественниками по цеху
										# Затем выставим наибольший финал и подгоним старты
										prev_order_hs = Order.objects.get(id=queue_hs[queue_hs.index(fix_order.id)-1])
										prev_order_cs = Order.objects.get(id=queue_cs[queue_hs.index(fix_order.id)-1])
										if fix_order.assumed_start_hs > prev_order_hs.assumed_finish:
											fix_order.assumed_start_hs = prev_order_hs.assumed_finish
											assumed_finish_hs = fix_order.assumed_start_hs + fix_order.cook_duration_hs
										else:
											assumed_finish_hs = fix_order.assumed_start_hs + fix_order.cook_duration_hs
										if fix_order.assumed_start_cs > prev_order_cs.assumed_finish:
											fix_order.assumed_start_cs = prev_order_cs.assumed_finish
											assumed_finish_cs = fix_order.assumed_start_cs + fix_order.cook_duration_cs
										else:
											assumed_finish_cs = fix_order.assumed_start_cs + fix_order.cook_duration_cs
										fix_order.assumed_finish = max(assumed_finish_hs, assumed_finish_cs)
										fix_order.assumed_start_hs = fix_order.assumed_finish - fix_order.cook_duration_hs
										fix_order.assumed_start_cs = fix_order.assumed_finish - fix_order.cook_duration_cs
										fix_order.save()
								break
					elif order.cook_duration_cs > timedelta(seconds=0):
						# Заказ находится целиком в очереди холодного цеха
						order_index = final_queue.index(order.id)
						order_index_cs = queue_cs.index(order.id)
						for i in range(order_index_cs):
							if queue_gaps_cs[i] > order.cook_duration_cs:
								# Нашли шаг, который можно сдвинуть. Очередь не оптимизирована (флаг на "Ложь")
								optimized_flag = False
								if i == 0:
									order.assumed_start_cs = initial_moment
									order.assumed_finish = initial_moment + order.cook_duration_cs
									order.assumed_start_hs = order.assumed_finish
								else:
									prev_order = Order.objects.get(id=queue_cs[i-1])
									order.assumed_start_cs = prev_order.assumed_finish
									order.assumed_finish = order.assumed_start_cs + order.cook_duration_cs
									order.assumed_start_hs = order.assumed_finish
								order.save()
								queue_cs.remove(order.id)
								queue_cs.insert(i, order.id)
								order_moved = True
								# Подправляем старты и финиши всех шагов после сдвинутого
								for i in range(order_index, len(final_queue)):
									fix_order = Order.objects.get(id = final_queue[i])
									# Если заказ целиком в одном цехе, то сверим с предыдущим шагом в очереди горячего цеха
									if fix_order.single_shop_flag == True:
										if fix_order.cook_duration_hs > timedelta(seconds=0):
											prev_order = Order.objects.get(id=queue_hs[queue_hs.index(fix_order.id)-1])
											if fix_order.assumed_start_hs > prev_order.assumed_finish:
												fix_order.assumed_start_hs = prev_order.assumed_finish
												fix_order.assumed_finish = fix_order.assumed_start_hs + fix_order.cook_duration_hs
												fix_order.assumed_start_cs = fix_order.assumed_finish
												fix_order.save()
										elif fix_order.cook_duration_cs > timedelta(seconds=0):
											prev_order = Order.objects.get(id=queue_cs[queue_cs.index(fix_order.id)-1])
											if fix_order.assumed_start_cs > prev_order.assumed_finish:
												fix_order.assumed_start_cs = prev_order.assumed_finish
												fix_order.assumed_finish = fix_order.assumed_start_cs + fix_order.cook_duration_cs
												fix_order.assumed_start_hs = fix_order.assumed_finish
												fix_order.save()
									else:
										# Если заказ в обоих цехах, то сверим части обеих цехов с их предшественниками по цеху
										# Затем выставим наибольший финал и подгоним старты
										prev_order_hs = Order.objects.get(id=queue_hs[queue_hs.index(fix_order.id)-1])
										prev_order_cs = Order.objects.get(id=queue_cs[queue_cs.index(fix_order.id)-1])
										if fix_order.assumed_start_hs > prev_order_hs.assumed_finish:
											fix_order.assumed_start_hs = prev_order_hs.assumed_finish
											assumed_finish_hs = fix_order.assumed_start_hs + fix_order.cook_duration_hs
										else:
											assumed_finish_hs = fix_order.assumed_start_hs + fix_order.cook_duration_hs
										if fix_order.assumed_start_cs > prev_order_cs.assumed_finish:
											fix_order.assumed_start_cs = prev_order_cs.assumed_finish
											assumed_finish_cs = fix_order.assumed_start_cs + fix_order.cook_duration_cs
										else:
											assumed_finish_cs = fix_order.assumed_start_cs + fix_order.cook_duration_cs
										fix_order.assumed_finish = max(assumed_finish_hs, assumed_finish_cs)
										fix_order.assumed_start_hs = fix_order.assumed_finish - fix_order.cook_duration_hs
										fix_order.assumed_start_cs = fix_order.assumed_finish - fix_order.cook_duration_cs
										fix_order.save()
								break
	final_queue, queue_hs, queue_cs = CreateThreeQueues()
	orders_list_hs = Order.objects.filter(finished=False, cook_duration_hs__gt=timedelta(seconds=0)).order_by('assumed_start_hs')
	orders_list_cs = Order.objects.filter(finished=False, cook_duration_cs__gt=timedelta(seconds=0)).order_by('assumed_start_cs')
	queue_gaps_hs = GetQueueGaps(initial_moment, orders_list_hs, queue_hs, "hs")
	queue_gaps_cs = GetQueueGaps(initial_moment, orders_list_cs, queue_cs, "cs")

	optimized_flag = False
	while optimized_flag == False:
		optimized_flag = True
		order_moved = False
		for idx, order in enumerate(final_queue):
			if order_moved == True:
				final_queue, queue_hs, queue_cs = CreateThreeQueues()
				orders_list_hs = Order.objects.filter(finished=False, cook_duration_hs__gt=timedelta(seconds=0)).order_by('assumed_start_hs')
				orders_list_cs = Order.objects.filter(finished=False, cook_duration_cs__gt=timedelta(seconds=0)).order_by('assumed_start_cs')
				queue_gaps_hs = GetQueueGaps(initial_moment, orders_list_hs, queue_hs, "hs")
				queue_gaps_cs = GetQueueGaps(initial_moment, orders_list_cs, queue_cs, "cs")
				break
			else:
				for i in range(len(final_queue)):
					fix_order = Order.objects.get(id = final_queue[i])
					# Если заказ целиком в одном цехе, то сверим с предыдущим шагом в очереди горячего цеха
					if fix_order.single_shop_flag == True:
						if fix_order.cook_duration_hs > timedelta(seconds=0):
							prev_order = Order.objects.get(id=queue_hs[queue_hs.index(fix_order.id)-1])
							if fix_order.assumed_start_hs > prev_order.assumed_finish:
								order_moved = True
								optimized_flag = False
								fix_order.assumed_start_hs = prev_order.assumed_finish
								fix_order.assumed_finish = fix_order.assumed_start_hs + fix_order.cook_duration_hs
								fix_order.assumed_start_cs = fix_order.assumed_finish
								fix_order.save()
						elif fix_order.cook_duration_cs > timedelta(seconds=0):
							prev_order = Order.objects.get(id=queue_cs[queue_cs.index(fix_order.id)-1])
							if fix_order.assumed_start_cs > prev_order.assumed_finish:
								order_moved = True
								optimized_flag = False
								fix_order.assumed_start_cs = prev_order.assumed_finish
								fix_order.assumed_finish = fix_order.assumed_start_cs + fix_order.cook_duration_cs
								fix_order.assumed_start_hs = fix_order.assumed_finish
								fix_order.save()
					else:
						# Если заказ в обоих цехах, то сверим части обеих цехов с их предшественниками по цеху
						# Затем выставим наибольший финал и подгоним старты
						prev_order_hs = Order.objects.get(id=queue_hs[queue_hs.index(fix_order.id)-1])
						prev_order_cs = Order.objects.get(id=queue_cs[queue_cs.index(fix_order.id)-1])
						if fix_order.assumed_start_hs > prev_order_hs.assumed_finish:
							fix_order.assumed_start_hs = prev_order_hs.assumed_finish
							assumed_finish_hs = fix_order.assumed_start_hs + fix_order.cook_duration_hs
						else:
							assumed_finish_hs = fix_order.assumed_start_hs + fix_order.cook_duration_hs
						if fix_order.assumed_start_cs > prev_order_cs.assumed_finish:
							fix_order.assumed_start_cs = prev_order_cs.assumed_finish
							assumed_finish_cs = fix_order.assumed_start_cs + fix_order.cook_duration_cs
						else:
							assumed_finish_cs = fix_order.assumed_start_cs + fix_order.cook_duration_cs
						old_finish = fix_order.assumed_finish
						fix_order.assumed_finish = max(assumed_finish_hs, assumed_finish_cs)
						if old_finish != fix_order.assumed_finish:
							order_moved = True
							optimized_flag = False
						fix_order.assumed_start_hs = fix_order.assumed_finish - fix_order.cook_duration_hs
						fix_order.assumed_start_cs = fix_order.assumed_finish - fix_order.cook_duration_cs
						fix_order.save()
	orders_list_hs = Order.objects.filter(finished=False, cook_duration_hs__gt=timedelta(seconds=0)).order_by('assumed_start_hs')
	orders_list_cs = Order.objects.filter(finished=False, cook_duration_cs__gt=timedelta(seconds=0)).order_by('assumed_start_cs')

	for order in orders_list_cs:
		order.delay = order.assumed_start_cs - initial_moment
		order.save()
		orderpos_list = OrderPosition.objects.filter(order = order, finished = False, dish__shop = "cold_shop").order_by("duration")
		for orderpos in orderpos_list:
			unfinished_steps = CookStepPosition.objects.filter(orderpos = orderpos, finished = False).order_by("cookstep__position")
			for step in unfinished_steps:
				count = 0
				for prev_step in CookStepPosition.objects.filter(orderpos = step.orderpos, cookstep__in = step.cookstep.previous_steps.all()):
					if prev_step.finished == True:
						count += 1
				if count == step.cookstep.previous_steps.all().count():
					inprogress_steps = inprogress_steps.union(CookStepPosition.objects.filter(cookstep = step.cookstep, orderpos = step.orderpos))

	if request.method == 'POST':
		if request.POST.get("ready", ""):
			step_id = request.POST.get("ready", "")
			step = CookStepPosition.objects.get(id=step_id)
			step.finished = True
			step.save()
			return redirect('queryapp:csqueue')
		if request.POST.get("return", ""):
			step_id = request.POST.get("return", "")
			step = CookStepPosition.objects.get(id=step_id)
			step.finished = False
			step.save()
			return redirect('queryapp:csqueue')

	context = {
		'csplaces': csplaces,
		'finished_steps': finished_steps,
		'inprogress_steps': inprogress_steps,
		'zero_duration': timedelta(seconds=0),
	}
	return HttpResponse(template.render(context, request))

@login_required
def addorder(request):
	template = loader.get_template('queryapp/addorder.html')
	dishes_list = Dish.objects.order_by('title')
	dishcat_list = DishCategory.objects.order_by('title')

	if request.method == 'GET':
		formset = OrderPositionFormset(request.GET or None)
	elif request.method == 'POST':
		formset = OrderPositionFormset(request.POST)
		if formset.is_valid():
			neworder = Order()
			neworder.save()
			for form in formset:
				dish_title = form.cleaned_data.get('dish')
				quantity = form.cleaned_data.get('quantity')
				if dish_title:
					dish = Dish.objects.get(title=dish_title)
					pos_duration = dish.cook_duration_max
					for cookstep in dish.cookstep_set.filter(multiply_time = True):
						pos_duration += cookstep.duration*(quantity-1)
					newpos = OrderPosition(order=neworder, dish=dish, quantity=quantity, duration=pos_duration)
					newpos.save()
					for cookstep in dish.cookstep_set.all().order_by('position'):
						cooksteppos = CookStepPosition(cookstep=cookstep, orderpos=newpos)
						cooksteppos.save()
			return redirect('queryapp:addorder')
	context = {
		'dishes_list': dishes_list,
		'dishcat_list': dishcat_list,
		'formset': formset,
	}
	return HttpResponse(template.render(context, request))
