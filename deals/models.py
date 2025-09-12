from django.db import models
from integration_utils.bitrix24.models import BitrixUser


class CustomDeal(models.Model):
    bitrix_id = models.IntegerField(unique=True, blank=True, null=True)
    title = models.CharField(max_length=255)
    custom_priority = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'deals'

    def __str__(self):
        return f"{self.title} (ID: {self.bitrix_id})"