import re
import phonenumbers
import pycountry
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

def validate_phone_number(value):
    """
    Validate phone number using the phonenumbers library.
    """
    if not value:
        return
    
    try:
        # Parse the phone number (assuming international format)
        phone_number = phonenumbers.parse(value, None)
        
        # Check if the phone number is valid
        if not phonenumbers.is_valid_number(phone_number):
            raise ValidationError(
                _('Enter a valid phone number.'),
                code='invalid_phone_number',
            )
    except phonenumbers.NumberParseException:
        raise ValidationError(
            _('Enter a valid phone number in international format (e.g., +1234567890).'),
            code='invalid_phone_format',
        )

def validate_password_strength(password):
    """
    Validate that the password meets strength requirements:
    - At least 8 characters
    - Contains at least one uppercase letter
    - Contains at least one lowercase letter
    - Contains at least one digit
    - Contains at least one special character
    """
    if len(password) < 8:
        raise ValidationError(
            _('Password must be at least 8 characters long.'),
            code='password_too_short',
        )
    
    if not re.search(r'[A-Z]', password):
        raise ValidationError(
            _('Password must contain at least one uppercase letter.'),
            code='password_no_upper',
        )
    
    if not re.search(r'[a-z]', password):
        raise ValidationError(
            _('Password must contain at least one lowercase letter.'),
            code='password_no_lower',
        )
    
    if not re.search(r'[0-9]', password):
        raise ValidationError(
            _('Password must contain at least one digit.'),
            code='password_no_digit',
        )
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValidationError(
            _('Password must contain at least one special character.'),
            code='password_no_symbol',
        )

def validate_country(value):
    """
    Validate that the country exists in the pycountry database.
    """
    if not value:
        return
    
    # Check if the country exists in pycountry database
    countries = [country.name for country in pycountry.countries]
    if value not in countries:
        raise ValidationError(
            _('Enter a valid country name.'),
            code='invalid_country',
        )