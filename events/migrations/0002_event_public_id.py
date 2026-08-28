import secrets
import string

from django.db import migrations, models

_ALPHABET = string.ascii_letters + string.digits


def _generate_public_id(length=10):
    return ''.join(secrets.choice(_ALPHABET) for _ in range(length))


def populate_public_ids(apps, schema_editor):
    Event = apps.get_model('events', 'Event')
    existing_ids = set()
    for event in Event.objects.all().order_by('pk'):
        public_id = _generate_public_id()
        while public_id in existing_ids:
            public_id = _generate_public_id()
        existing_ids.add(public_id)
        event.public_id = public_id
        event.save(update_fields=['public_id'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='public_id',
            field=models.CharField(blank=True, default='', max_length=10, db_index=False),
        ),
        migrations.RunPython(populate_public_ids, noop),
        migrations.AlterField(
            model_name='event',
            name='public_id',
            field=models.CharField(blank=True, editable=False, max_length=10, unique=True),
        ),
    ]
