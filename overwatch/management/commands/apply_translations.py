"""Management command to apply DataDictionary translations to existing servers."""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from overwatch.models import Server


class Command(BaseCommand):
    help = "Apply DataDictionary translations to all existing servers (ADMIN ONLY)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without actually updating",
        )
        parser.add_argument(
            "--user",
            type=str,
            help="Username to verify admin status (optional, for verification)",
        )

    def handle(self, *args, **options):
        # Check if any superusers exist (admin-only command)
        if not User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.ERROR(
                    "ERROR: This command can only be run by site administrators. No superusers found in system."
                )
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS(
                "✓ Admin verification passed. Proceeding with translation updates..."
            )
        )
        
        dry_run = options["dry_run"]
        
        servers = Server.objects.all()
        total = servers.count()
        updated = 0
        
        self.stdout.write(f"Processing {total} servers...")
        
        for server in servers:
            # Store original values
            original_manufacture = server.manufacture
            original_product = server.product_name
            original_cpu = server.cpu
            original_os = server.os
            
            if dry_run:
                # Call translate methods without saving
                new_manufacture = server._translate_field("manufacture", original_manufacture) if original_manufacture else None
                new_product = server._translate_field("product_name", original_product) if original_product else None
                new_cpu = server._translate_field("cpu", original_cpu) if original_cpu else None
                new_os = server._translate_field("os", original_os) if original_os else None
                
                changes = []
                if new_manufacture and new_manufacture != original_manufacture:
                    changes.append(f"  Manufacture: {original_manufacture} → {new_manufacture}")
                if new_product and new_product != original_product:
                    changes.append(f"  Product:     {original_product} → {new_product}")
                if new_cpu and new_cpu != original_cpu:
                    changes.append(f"  CPU:         {original_cpu} → {new_cpu}")
                if new_os and new_os != original_os:
                    changes.append(f"  OS:          {original_os} → {new_os}")
                
                if changes:
                    self.stdout.write(f"\n{server.hostname} (ID: {server.id})")
                    for change in changes:
                        self.stdout.write(change)
                    updated += 1
            else:
                # Actually save to trigger translations
                server.save()
                
                # Check if anything changed
                server.refresh_from_db()
                changed = (
                    server.manufacture != original_manufacture or
                    server.product_name != original_product or
                    server.cpu != original_cpu or
                    server.os != original_os
                )
                
                if changed:
                    self.stdout.write(self.style.SUCCESS(f"✓ Updated: {server.hostname}"))
                    updated += 1
        
        if dry_run:
            self.stdout.write(f"\n[DRY RUN] Would update {updated} of {total} servers")
            self.stdout.write("Run without --dry-run to apply changes")
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✓ Successfully updated {updated} of {total} servers"))
