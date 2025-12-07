from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("overwatch", "0007_many_to_many_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="server",
            name="pdu_ip",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="server",
            name="pdu_port_number",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
