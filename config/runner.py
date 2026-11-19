"""
Custom Test Runner for Smart HRMS.
"""
from django.conf import settings
from django.test.runner import DiscoverRunner


class SmartHRTestRunner(DiscoverRunner):
    """
    Custom DiscoverRunner for Smart HRMS.
    Ensures that default test discovery anchors at BASE_DIR, preventing
    discovery from traversing up to parent directories (such as Desktop).
    """

    def __init__(self, *args, **kwargs):
        if not kwargs.get("top_level"):
            kwargs["top_level"] = str(settings.BASE_DIR)
        super().__init__(*args, **kwargs)
