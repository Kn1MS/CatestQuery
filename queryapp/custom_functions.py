from .models import *
from django.db.models.functions import Least

def CalculateDeeper(cur_step, cur_list, paths_list):
	cur_list.append(cur_step.position)
	if cur_step.previous_steps.all():
		for step in cur_step.previous_steps.all():
			CalculateDeeper(step, cur_list[:], paths_list)
	else:
		paths_list.append(cur_list)


def CalculatePaths(dish, finalpos):
	final_step = CookStep.objects.get(dish = dish, position = finalpos)
	paths_list = []
	current_list = [finalpos]
	if final_step.previous_steps.all():
		for step in final_step.previous_steps.all():
			CalculateDeeper(step, current_list[:], paths_list)
	else:
		paths_list.append(current_list)
	return paths_list

def GetQueueGaps(initial_moment, orders_list, queue, shop):
	queue_gaps = []
	for idx, order in enumerate(orders_list):
		cur_order = Order.objects.get(id = order.id)
		if idx == 0:
			if shop == "hot_shop" or shop == "hs":
				difference = cur_order.assumed_start_hs - initial_moment
			elif shop == "cold_shop" or shop == "cs":
				difference = cur_order.assumed_start_cs - initial_moment
			queue_gaps.append(difference)
		else:
			prev_order = Order.objects.get(id = queue[idx - 1])
			if shop == "hot_shop" or shop == "hs":
				difference = cur_order.assumed_start_hs - prev_order.assumed_finish
			elif shop == "cold_shop" or shop == "cs":
				difference = cur_order.assumed_start_cs - prev_order.assumed_finish
			queue_gaps.append(difference)
	return queue_gaps

def CreateThreeQueues():
	new_orders_list = Order.objects.filter(finished=False).annotate(
		early_start=Least('assumed_start_hs', 'assumed_start_cs')
		).order_by('early_start')
	orders_list_hs = Order.objects.filter(finished=False, cook_duration_hs__gt=timedelta(seconds=0)).order_by('assumed_start_hs')
	orders_list_cs = Order.objects.filter(finished=False, cook_duration_cs__gt=timedelta(seconds=0)).order_by('assumed_start_cs')

	final_queue = []
	queue_hs = []
	queue_cs = []

	for order in new_orders_list:
		final_queue.append(order.id)
	for order in orders_list_hs:
		queue_hs.append(order.id)
	for order in orders_list_cs:
		queue_cs.append(order.id)
	return final_queue, queue_hs, queue_cs