import re

from django.views.debug import SafeExceptionReporterFilter


class ExceptionReporterFilter(SafeExceptionReporterFilter):
    """
    Django's error pages hide settings and environment variables whose names
    contain words such as KEY, SECRET or PASS. Connection strings carry an
    account key but match none of those words, so hide them as well.
    """

    hidden_settings = re.compile(
        SafeExceptionReporterFilter.hidden_settings.pattern + "|CONNECTION",
        flags=re.IGNORECASE,
    )
