from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Review, recalculate_company_rating


# recalculates the reviewee's CompanyRating whenever a new review is saved
@receiver(post_save, sender=Review)
def update_company_rating(sender, instance, **kwargs):
    recalculate_company_rating(instance.reviewee)
