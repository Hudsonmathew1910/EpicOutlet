from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms

from .models import Order, ProductReview


class CustomUserForm(UserCreationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose a username', 'autocomplete': 'username'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'you@example.com', 'autocomplete': 'email'}))
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create a password', 'autocomplete': 'new-password'}))
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Repeat the password', 'autocomplete': 'new-password'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'family-name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Another account already uses this email.')
        return email


INDIAN_STATES = [
    'Andaman and Nicobar Islands', 'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chandigarh',
    'Chhattisgarh', 'Dadra and Nagar Haveli and Daman and Diu', 'Delhi', 'Goa', 'Gujarat', 'Haryana',
    'Himachal Pradesh', 'Jammu and Kashmir', 'Jharkhand', 'Karnataka', 'Kerala', 'Ladakh', 'Lakshadweep',
    'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Puducherry',
    'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand',
    'West Bengal',
]


class CheckoutForm(forms.ModelForm):
    state = forms.ChoiceField(choices=[('', 'Select state')] + [(s, s) for s in INDIAN_STATES],
                              widget=forms.Select(attrs={'class': 'form-select', 'autocomplete': 'address-level1'}))

    class Meta:
        model = Order
        fields = ['full_name', 'email', 'phone', 'address_line1', 'address_line2', 'city', 'state', 'pincode']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'tel-national', 'inputmode': 'numeric', 'maxlength': 10, 'placeholder': '10-digit mobile'}),
            'address_line1': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'address-line1', 'placeholder': 'House no., street'}),
            'address_line2': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'address-line2', 'placeholder': 'Area, landmark (optional)'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'address-level2'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'postal-code', 'inputmode': 'numeric', 'maxlength': 6}),
        }

    def clean_full_name(self):
        return ' '.join(self.cleaned_data['full_name'].split())

    def clean_phone(self):
        return self.cleaned_data['phone'].strip().replace(' ', '')


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(i, f'{i} star{"s" if i > 1 else ""}') for i in range(5, 0, -1)],
        coerce=int, widget=forms.RadioSelect,
    )

    class Meta:
        model = ProductReview
        fields = ['rating', 'title', 'body']
        labels = {'title': 'Headline', 'body': 'Your review'}
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sum it up in a few words', 'maxlength': 120}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'maxlength': 1000,
                                          'placeholder': 'What did you like or dislike?'}),
        }
