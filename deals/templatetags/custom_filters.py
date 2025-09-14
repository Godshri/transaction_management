from django import template
import re

register = template.Library()

@register.filter
def clean_whitespace(value):
    """Удаляет лишние пробелы и переносы строк"""
    if not value:
        return value
    # Заменяем множественные переносы строк на один пробел
    value = re.sub(r'\n\s*\n', '\n', str(value))
    # Заменяем одиночные переносы строк на пробел
    #value = re.sub(r'\n', ' ', value)
    # Заменяем множественные пробелы на один
    value = re.sub(r' +', ' ', value)
    # Убираем пробелы в начале и конце
    value = value.strip()
    return value