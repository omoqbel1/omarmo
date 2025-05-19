from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_savedcarrier_cancellation_date_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='savedcarrier',
            name='coverage_from',
            field=models.CharField(blank=True, null=True, max_length=50),
        ),
        migrations.AlterField(
            model_name='savedcarrier',
            name='coverage_to',
            field=models.CharField(blank=True, null=True, max_length=50),
        ),
    ]
