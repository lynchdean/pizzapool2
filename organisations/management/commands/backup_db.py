import gzip
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Dump the database to a timestamped, gzip-compressed JSON fixture."

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', default=str(settings.BASE_DIR / 'backups'))

    def handle(self, *args, **options):
        output_dir = Path(options['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        backup_path = output_dir / f"backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json.gz"

        with gzip.open(backup_path, 'wt') as f:
            call_command('dumpdata', stdout=f)

        self.stdout.write(self.style.SUCCESS(f'Backup written to {backup_path}'))
