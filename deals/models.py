from django.db import models
from integration_utils.bitrix24.models import BitrixUser
import uuid
from django.urls import reverse
from django.core.files.storage import FileSystemStorage


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
    product_images = models.JSONField(null=True, blank=True)
    created_by = models.ForeignKey(BitrixUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'deals'

    def __str__(self):
        return f"{self.product_name} - {self.created_at}"

    def get_absolute_url(self):
        return reverse('product_qr_detail', kwargs={'uuid': str(self.id)})


class ImportExportJob(models.Model):
    JOB_TYPE_IMPORT = 'import'
    JOB_TYPE_EXPORT = 'export'
    JOB_TYPE_CHOICES = [
        (JOB_TYPE_IMPORT, 'Импорт'),
        (JOB_TYPE_EXPORT, 'Экспорт'),
    ]

    FORMAT_CSV = 'csv'
    FORMAT_XLSX = 'xlsx'
    FORMAT_CHOICES = [
        (FORMAT_CSV, 'CSV'),
        (FORMAT_XLSX, 'XLSX'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Ожидание'),
        (STATUS_PROCESSING, 'В процессе'),
        (STATUS_COMPLETED, 'Завершено'),
        (STATUS_FAILED, 'Ошибка'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_type = models.CharField(max_length=10, choices=JOB_TYPE_CHOICES)
    file_format = models.CharField(max_length=10, choices=FORMAT_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_by = models.ForeignKey(BitrixUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_records = models.IntegerField(default=0)
    processed_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    file_name = models.CharField(max_length=255)
    filter_params = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    export_file = models.FileField(
        upload_to='export_files/',
        null=True,
        blank=True,
        storage=FileSystemStorage(location='media/export_files')
    )

    class Meta:
        ordering = ['-created_at']

    def get_job_type_display(self):
        """Отображаемое название типа задачи"""
        return dict(self.JOB_TYPE_CHOICES).get(self.job_type, self.job_type)

    def get_status_display(self):
        """Отображаемое название статуса"""
        return dict(self.STATUS_CHOICES).get(self.status, self.status)


class ImportExportRecord(models.Model):
    job = models.ForeignKey(ImportExportJob, on_delete=models.CASCADE, related_name='records')
    record_index = models.IntegerField()
    contact_data = models.JSONField()
    bitrix_contact_id = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['record_index']

