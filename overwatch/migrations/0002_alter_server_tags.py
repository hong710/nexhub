from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("overwatch", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="server",
            name="tags",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
