import secrets
import string

from django.db import migrations, models

_ALPHABET = string.ascii_letters + string.digits


def _generate_public_id(length=10):
    return ''.join(secrets.choice(_ALPHABET) for _ in range(length))


def populate_public_ids(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    existing_ids = set()
    for order in Order.objects.all().order_by('pk'):
        public_id = _generate_public_id()
        while public_id in existing_ids:
            public_id = _generate_public_id()
        existing_ids.add(public_id)
        order.public_id = public_id
        order.save(update_fields=['public_id'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_portion_claimant_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='public_id',
            field=models.CharField(blank=True, default='', max_length=10, db_index=False),
        ),
        migrations.RunPython(populate_public_ids, noop),
        migrations.AlterField(
            model_name='order',
            name='public_id',
            field=models.CharField(blank=True, editable=False, max_length=10, unique=True),
        ),
    ]
