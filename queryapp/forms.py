from django import forms
from django.forms import formset_factory

class OrderPositionForm(forms.Form):
    dish = forms.CharField(
        label='123',
        widget=forms.TextInput(attrs={
            'class': 'dish',
        })
    )
    quantity = forms.IntegerField(
    	label='123',
    	widget=forms.NumberInput(attrs={
            'class': 'quantity',
        })
    )

OrderPositionFormset = formset_factory(OrderPositionForm, extra=1)