from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("overwatch", "0005_tag_server"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="server",
            name="tags",
        ),
        migrations.RemoveField(
            model_name="server",
            name="tags_m2m",
        ),
        migrations.AlterField(
            model_name="tag",
            name="server",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name="tag_links",
                to="overwatch.server",
                to_field="uuid",
            ),
        ),
    ]
