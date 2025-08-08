from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Custom User model that extends the default Django User model.
    """

    ROLE_CHOICES = [
        ("helpdesk", "Helpdesk"),
        ("ceo", "CEO"),
    ]

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default="helpdesk",
        help_text=_("User's role in the system"),
    )

    def __str__(self):
        return self.username

    @property
    def is_helpdesk(self):
        return self.role == "helpdesk"

    @property
    def is_ceo(self):
        return self.role == "ceo"
