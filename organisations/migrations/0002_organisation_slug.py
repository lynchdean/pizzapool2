from django.db import migrations, models
from django.utils.text import slugify


def populate_slugs(apps, schema_editor):
    Organisation = apps.get_model('organisations', 'Organisation')
    existing_slugs = set()
    for org in Organisation.objects.all().order_by('pk'):
        base_slug = slugify(org.name)
        slug = base_slug
        n = 2
        while slug in existing_slugs:
            slug = f"{base_slug}-{n}"
            n += 1
        existing_slugs.add(slug)
        org.slug = slug
        org.save(update_fields=['slug'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('organisations', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organisation',
            name='name',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AddField(
            model_name='organisation',
            name='slug',
            field=models.CharField(blank=True, default='', max_length=255, db_index=False),
        ),
        migrations.RunPython(populate_slugs, noop),
        migrations.AlterField(
            model_name='organisation',
            name='slug',
            field=models.SlugField(blank=True, max_length=255, unique=True),
        ),
    ]
