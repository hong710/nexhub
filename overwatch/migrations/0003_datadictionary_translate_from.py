from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("overwatch", "0002_alter_server_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="datadictionary",
            name="translate_from",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
