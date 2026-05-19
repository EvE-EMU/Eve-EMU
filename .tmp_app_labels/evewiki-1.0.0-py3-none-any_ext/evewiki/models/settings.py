from django.db import models


class Setting(models.Model):
    """
    Settings and feature flags.
    """

    hierarchy_max_display_depth = models.IntegerField(
        default=3,
        null=False,
        help_text="Limit the depth of the tree for the hierarchy on the main display",
    )

    max_versions = models.IntegerField(
        default=100,
        null=False,
        help_text="No one has infinite disk space, a sensible limit which can be modified to clear down the history",
    )

    def get_settings():
        """
        Returns the Setting instance with the lowest id,
        or a default Setting instance (not saved) if none exist.
        """
        setting = Setting.objects.order_by("id").first()
        if setting is not None:
            return setting

        return Setting(
            hierarchy_max_display_depth=Setting._meta.get_field(
                "hierarchy_max_display_depth"
            ).get_default(),
            max_versions=Setting._meta.get_field("max_versions").get_default(),
        )
