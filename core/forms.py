from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UsernameField
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.contrib.auth.models import User
from django import forms


class StyledAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = (
                'w-full rounded-lg border border-slate-300 bg-slate-50 '
                'px-4 py-2.5 text-slate-900 focus:outline-none focus:ring-2 '
                'focus:ring-indigo-500'
            )


class SignUpForm(UserCreationForm):
    username = UsernameField(
        max_length=20,
        validators=[UnicodeUsernameValidator(message='Enter a valid username')],
        help_text=(
            'Up to 20 characters. Use letters and numbers, plus @, ., +, - or _.'
        ),
    )
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = (
                'w-full rounded-lg border border-slate-300 bg-slate-50 '
                'px-4 py-2.5 text-slate-900 focus:outline-none focus:ring-2 '
                'focus:ring-indigo-500'
            )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user
