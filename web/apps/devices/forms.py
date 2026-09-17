from django import forms
from .models import Device

class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ['name', 'mac_address', 'location_name', 'weather_location', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'mac_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 68:09:47:4E:75:F0'}),
            'location_name': forms.TextInput(attrs={'class': 'form-control'}),
            'weather_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., London, Tokyo, New York'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
