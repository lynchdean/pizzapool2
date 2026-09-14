from django import template

register = template.Library()


@register.inclusion_tag('components/loading_icon.html')
def loading_icon(n=3):
    """Three logo marks arranged like pizza slices (top, left, right); n (0-3) lights them in that order."""
    n = max(0, min(3, n))
    return {
        'lit_count': n,
        'top_lit': n >= 1,
        'left_lit': n >= 2,
        'right_lit': n >= 3,
    }
