from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def page_querystring(context):
    """Current GET filters without page=, for pagination links."""
    request = context.get("request")
    if request is None:
        return ""
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()