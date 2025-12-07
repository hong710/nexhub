from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("overwatch", "0004_tag"),
    ]

    operations = [
        migrations.AddField(
            model_name="tag",
            name="server",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name="tag_links",
                to="overwatch.server",
            ),
        ),
    ]
