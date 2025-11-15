from django import forms
from .models import Order, OrderItem, MenuItem


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['order_type', "table_number", "comment",]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.menu_items = MenuItem.objects.all().select_related("category")
        for item in self.menu_items:
            self.fields[f"item_{item.id}"] = forms.IntegerField(
                label=f"{item.name} {item.price}",
                min_value=0,
                initial=0,
                required=False,
                widget=forms.NumberInput(
                    attrs={"class": "item-quantity", "data-price": item.price}
                ),
            )
        
        # Настройка поля комментария
        self.fields['comment'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Например: без лука, срочно, на 2 этаж...',
            'rows': 2
        })
        self.fields['comment'].required = False

