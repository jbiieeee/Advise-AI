from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from django.conf import settings

class Command(BaseCommand):
    help = 'Ensures the default Site object exists for allauth'

    def handle(self, *args, **options):
        site_id = getattr(settings, 'SITE_ID', 1)
        domain = 'advise-ai.onrender.com'
        name = 'Advise-AI'
        
        site, created = Site.objects.get_or_create(
            id=site_id,
            defaults={'domain': domain, 'name': name}
        )
        
        if not created:
            site.domain = domain
            site.name = name
            site.save()
            self.stdout.write(self.style.SUCCESS(f'Updated site: {domain}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Created site: {domain}'))
