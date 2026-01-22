from django.db import models

class AppVersion(models.Model):
    version = models.CharField(max_length=50, help_text="e.g. 1.0.0")
    force_update = models.BooleanField(default=False)
    message = models.TextField(blank=True, help_text="Message to show in the update dialog")
    store_url = models.URLField(blank=True, help_text="Link to Play Store / App Store")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Version {self.version} (Force: {self.force_update})"

    class Meta:
        get_latest_by = 'created_at'