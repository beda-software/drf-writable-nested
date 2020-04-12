def pytest_configure():
    try:
        import django
        django.setup()
    except AttributeError:
        pass
