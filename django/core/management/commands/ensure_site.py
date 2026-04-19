from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from django.conf import settings
from allauth.socialaccount.models import SocialApp
import os

class Command(BaseCommand):
    help = 'Ensures the default Site object exists and provisions SocialApps for allauth'

    def handle(self, *args, **options):
        # 1. Diagnostic & Cleanup
        self.stdout.write("--- DATABASE DIAGNOSTICS ---")
        all_sites = Site.objects.all()
        self.stdout.write(f"Existing Sites: {[f'ID:{s.id} {s.domain}' for s in all_sites]}")
        
        all_apps = SocialApp.objects.all()
        self.stdout.write(f"Existing SocialApps: {[f'ID:{a.id} {a.provider}' for a in all_apps]}")

        # NUCLEAR WIPE
        SocialApp.objects.all().delete()
        self.stdout.write(self.style.WARNING("Nuclear Wipe: Deleted all SocialApps."))
        
        # Site Provisioning
        site_id = getattr(settings, 'SITE_ID', 1)
        domain = os.environ.get('SITE_DOMAIN', 'advise-ai.onrender.com')
        name = 'Advise-AI'
        
        # Ensure we only have ONE site with this ID
        Site.objects.filter(id=site_id).delete()
        site = Site.objects.create(id=site_id, domain=domain, name=name)
        self.stdout.write(self.style.SUCCESS(f"Re-provisioned Site ID {site_id}: {domain}"))

        # 2. Social Apps Re-provisioning fresh
        providers = {
            'google': {
                'client_id': os.environ.get('SOCIAL_AUTH_GOOGLE_CLIENT_ID'),
                'secret': os.environ.get('SOCIAL_AUTH_GOOGLE_SECRET'),
                'name': 'Google'
            },
            'github': {
                'client_id': os.environ.get('SOCIAL_AUTH_GITHUB_CLIENT_ID'),
                'secret': os.environ.get('SOCIAL_AUTH_GITHUB_SECRET'),
                'name': 'GitHub'
            },
            'facebook': {
                'client_id': os.environ.get('SOCIAL_AUTH_FACEBOOK_CLIENT_ID'),
                'secret': os.environ.get('SOCIAL_AUTH_FACEBOOK_SECRET'),
                'name': 'Facebook'
            }
        }

        for provider, config in providers.items():
            if config['client_id'] and config['secret']:
                app = SocialApp.objects.create(
                    provider=provider,
                    name=config['name'],
                    client_id=config['client_id'],
                    secret=config['secret']
                )
                app.sites.add(site)
                self.stdout.write(self.style.SUCCESS(f'Provisioned fresh {config["name"]} linked to {domain}'))
            else:
                self.stdout.write(self.style.WARNING(f'Skipping {config["name"]}: Missing env vars.'))
