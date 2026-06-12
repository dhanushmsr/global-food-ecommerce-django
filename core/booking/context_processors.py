# Save this strictly inside booking/context_processors.py
def language_context(request):
    """Automatically passes the current session language string to all HTML templates."""
    return {
        'lang': request.session.get('lang', 'de')
    }