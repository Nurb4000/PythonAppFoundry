"""Input validation utilities for the platform."""
import re
from slugify import slugify


def validate_slug(value):
    """Validate that a string is a valid URL-safe slug."""
    if not value:
        return False, 'Slug cannot be empty'
    normalized = slugify(value)
    if normalized != value:
        return False, f'Slug must contain only letters, numbers, hyphens, and underscores (got "{normalized}")'
    if len(value) > 200:
        return False, 'Slug must be 200 characters or less'
    return True, None


def validate_route_slug(value):
    """Validate a route slug (URL path)."""
    if not value:
        return False, 'Route slug cannot be empty'
    # Must start with /
    if not value.startswith('/'):
        value = '/' + value
    # Remove trailing slash (except for root)
    if value != '/' and value.endswith('/'):
        value = value.rstrip('/')
    # Validate characters
    if not re.match(r'^[a-zA-Z0-9/_-]+$', value):
        return False, 'Route slug can only contain letters, numbers, hyphens, underscores, and forward slashes'
    if len(value) > 500:
        return False, 'Route slug must be 500 characters or less'
    return True, value


def validate_cron_expression(expr):
    """Validate a 5-field cron expression."""
    if not expr:
        return False, 'Cron expression cannot be empty'
    parts = expr.strip().split()
    if len(parts) != 5:
        return False, 'Cron expression must have exactly 5 fields (minute hour day month day_of_week)'
    
    minute, hour, day, month, dow = parts
    
    def _validate_field(field, min_val, max_val, name):
        if field == '*':
            return True, None
        for part in field.split(','):
            if '-' in part:
                a, b = part.split('-', 1)
                if not (a.isdigit() and b.isdigit()):
                    return False, f'{name} field "{part}" must be numeric range'
                if not (int(a) <= int(b) <= max_val):
                    return False, f'{name} field range out of bounds ({min_val}-{max_val})'
            elif part.startswith('*/'):
                if not part[2:].isdigit():
                    return False, f'{name} field "{part}" must have numeric step'
            elif part.startswith('*'):
                return False, f'{name} field "{part}" is not valid'
            elif not part.isdigit():
                return False, f'{name} field "{part}" must be a number, *, range, or step'
        return True, None
    
    for field, min_val, max_val, name in [
        (minute, 0, 59, 'Minute'),
        (hour, 0, 23, 'Hour'),
        (day, 1, 31, 'Day'),
        (month, 1, 12, 'Month'),
        (dow, 0, 6, 'Day of week'),
    ]:
        valid, err = _validate_field(field, min_val, max_val, name)
        if not valid:
            return False, err
    
    return True, None


def validate_email(value):
    """Basic email validation."""
    if not value:
        return False, 'Email cannot be empty'
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, value):
        return False, 'Invalid email format'
    return True, None


def validate_username(value):
    """Validate username."""
    if not value:
        return False, 'Username cannot be empty'
    if len(value) < 3 or len(value) > 80:
        return False, 'Username must be between 3 and 80 characters'
    if not re.match(r'^[a-zA-Z0-9_-]+$', value):
        return False, 'Username can only contain letters, numbers, hyphens, and underscores'
    return True, None
