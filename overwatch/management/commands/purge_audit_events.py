from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from overwatch.models import AuditEvent


class Command(BaseCommand):
    help = "Purge AuditEvent records older than 90 days"

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=90)
        deleted, _ = AuditEvent.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"Purged {deleted} audit events older than 90 days"))
