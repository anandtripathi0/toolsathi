from django.core.management.base import BaseCommand
from apps.downloads.results import cleanup_results

class Command(BaseCommand):
    help = 'Delete expired temporary results; schedule once per minute in production.'
    def handle(self, **options):
        self.stdout.write(f'Removed {cleanup_results()} expired output files.')
