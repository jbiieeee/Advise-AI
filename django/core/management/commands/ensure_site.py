from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from django.conf import settings
from allauth.socialaccount.models import SocialApp
import os

class Command(BaseCommand):
    help = 'Ensures the default Site object exists and provisions SocialApps for allauth'

    def handle(self, *args, **options):
        # 1. Site Configuration
        site_id = getattr(settings, 'SITE_ID', 1)
        domain = os.environ.get('SITE_DOMAIN', 'advise-ai.onrender.com')
        name = 'Advise-AI'
        
        site, created = Site.objects.get_or_create(
            id=site_id,
            defaults={'domain': domain, 'name': name}
        )
        
        if not created:
            if site.domain != domain or site.name != name:
                site.domain = domain
                site.name = name
                site.save()
                self.stdout.write(self.style.SUCCESS(f'Updated site: {domain}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Created site: {domain}'))

        # 2. Social Apps Configuration - NUCLEAR CLEANUP
        # Delete all existing apps first to ensure no duplicates exist in the DB
        SocialApp.objects.all().delete()
        self.stdout.write(self.style.WARNING('Cleaned all existing SocialApps to resolve duplicates.'))

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
                # Find all existing apps for this provider
                existing_apps = SocialApp.objects.filter(provider=provider)
                
                if existing_apps.exists():
                    # If multiple exist, we need to clean up duplicates
                    if existing_apps.count() > 1:
                        self.stdout.write(self.style.WARNING(f'Found {existing_apps.count()} duplicate apps for {provider}. Cleaning up...'))
                        # Keep the first one, delete the rest
                        app = existing_apps.first()
                        existing_apps.exclude(id=app.id).delete()
                    else:
                        app = existing_apps.first()

                    # Update credentials if they changed
                    if app.client_id != config['client_id'] or app.secret != config['secret']:
                        app.client_id = config['client_id']
                        app.secret = config['secret']
                        app.save()
                        self.stdout.write(self.style.SUCCESS(f'Updated {config["name"]} credentials'))
                    else:
                        self.stdout.write(self.style.SUCCESS(f'{config["name"]} is already up to date'))
                else:
                    # Create new if none exists
                    app = SocialApp.objects.create(
                        provider=provider,
                        name=config['name'],
                        client_id=config['client_id'],
                        secret=config['secret']
                    )
                    self.stdout.write(self.style.SUCCESS(f'Provisioned {config["name"]} SocialApp'))
                
                # Ensure the app is linked to the site
                if not app.sites.filter(id=site.id).exists():
                    app.sites.add(site)
                    self.stdout.write(self.style.SUCCESS(f'Linked {config["name"]} to site {domain}'))
            else:
                self.stdout.write(self.style.WARNING(f'Skipping {config["name"]}: client_id or secret is not set in environment.'))
