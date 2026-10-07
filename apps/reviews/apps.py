from django.apps import AppConfig


# reviews app — Review submissions, CompanyRating denormalization, and public profiles
class ReviewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reviews'
    label = 'reviews'

    def ready(self):
        import apps.reviews.signals  # noqa: F401
