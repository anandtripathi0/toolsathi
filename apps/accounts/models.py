from django.conf import settings
from django.db import models

class Preferences(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    favorites = models.JSONField(default=list)
    history_enabled = models.BooleanField(default=False)
    recent = models.JSONField(default=list)

class RateBucket(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    count = models.PositiveIntegerField(default=0)
    expires = models.BigIntegerField(db_index=True)
