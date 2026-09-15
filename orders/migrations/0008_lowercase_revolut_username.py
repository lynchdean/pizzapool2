from django.db import migrations


def lowercase_revolut_username(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    for order in Order.objects.exclude(revolut_username__isnull=True).exclude(revolut_username=''):
        lowered = order.revolut_username.lower()
        if lowered != order.revolut_username:
            order.revolut_username = lowered
            order.save(update_fields=['revolut_username'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0007_order_started_by_phone'),
    ]

    operations = [
        migrations.RunPython(lowercase_revolut_username, noop),
    ]
