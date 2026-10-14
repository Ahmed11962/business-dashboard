from django.core.management.base import BaseCommand
from core.seed import seed
class Command(BaseCommand):
    help='Create unverified starting facts and pending invitations; no users or posted balances.'
    def add_arguments(self,parser): parser.add_argument('--demo',action='store_true')
    def handle(self,*args,**options):
        d=seed(options['demo']); self.stdout.write(f'{d.name}: {d.pk}; no live users or financial postings created.')
