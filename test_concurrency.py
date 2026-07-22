# test_concurrency.py — run with: python manage.py shell < test_concurrency.py
# or better, as a quick script via `python manage.py runscript` if you have django-extensions,
# or just paste into shell_plus / shell

import threading
from orders.services import claim_portion, PortionAlreadyClaimedError
from orders.models import Portion

portion = Portion.objects.filter(claimant_name__isnull=True).first()
results = []

def try_claim(name):
    try:
        claim_portion(portion.id, name)
        results.append(f"{name}: SUCCESS")
    except PortionAlreadyClaimedError:
        results.append(f"{name}: BLOCKED")

threads = [threading.Thread(target=try_claim, args=(f"user{i}",)) for i in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(results)