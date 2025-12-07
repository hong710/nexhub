from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("overwatch", "0006_remove_server_tags_remove_server_tags_m2m_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="tag",
            name="server",
        ),
        migrations.AddField(
            model_name="server",
            name="tags",
            field=models.ManyToManyField(blank=True, related_name="servers", to="overwatch.tag"),
        ),
    ]
