from django.db import models
from integration_utils.bitrix24.models import BitrixUser
import uuid
from django.urls import reverse


class CustomDeal(models.Model):
    bitrix_id = models.IntegerField(unique=True, blank=True, null=True)
    title = models.CharField(max_length=255)
    custom_priority = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'deals'

    def __str__(self):
        return f"{self.title} (ID: {self.bitrix_id})"


class ProductQRLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product_id = models.IntegerField()
    product_name = models.CharField(max_length=255)
    product_data = models.JSONField(null=True, blank=True)
    created_by = models.ForeignKey(BitrixUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'deals'

    def __str__(self):
        return f"{self.product_name} - {self.created_at}"

    def get_absolute_url(self):
        return reverse('product_qr_detail', kwargs={'uuid': str(self.id)})