import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Custom manager for the ``User`` model.

    Provides ``create_user()`` and ``create_superuser()`` using
    ``email`` as the primary identifier.
    """

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        """Create and return a regular user with the given *email* and *password*."""
        if not email:
            raise ValueError("The Email field must be set.")
        email = self.normalize_email(email)
        if "username" not in extra_fields or not extra_fields["username"]:
            extra_fields["username"] = email.split("@")[0]
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        """Create and return a superuser with *email* and *password*."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_merchant", False)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model for MerchantHub.

    Uses **email** as the primary login identifier instead of a username.
    A unique ``username`` field is still maintained for Django compatibility
    (admin, groups, permissions) and as a display-friendly identifier.

    Primary key is a UUID v4 for security (non-predictable IDs),
    distributed-readiness, and safe database merging.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(
        unique=True,
        max_length=254,
        help_text=_("Primary login identifier. Must be unique."),
        error_messages={"unique": _("A user with this email address already exists.")},
    )

    username = models.CharField(
        max_length=150,
        unique=True,
        help_text=_("Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."),
        validators=[UnicodeUsernameValidator()],
        error_messages={"unique": _("A user with that username already exists.")},
    )

    first_name = models.CharField(max_length=150, blank=True, help_text=_("Given name."))
    last_name = models.CharField(max_length=150, blank=True, help_text=_("Family name."))
    phone_number = models.CharField(
        max_length=20, null=True, blank=True, help_text=_("Contact phone number (E.164 format recommended).")
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_("Designates whether this user can log into the platform. Unselect this instead of deleting accounts."),
    )
    is_staff = models.BooleanField(
        default=False, help_text=_("Designates whether the user can log into the Django admin site.")
    )
    is_merchant = models.BooleanField(
        default=True,
        help_text=_("Indicates whether the user registered as a business owner. Super-admins have this set to False."),
    )
    email_verified = models.BooleanField(
        default=False, help_text=_("Whether the user's email address has been verified.")
    )

    created_at = models.DateTimeField(auto_now_add=True, help_text=_("Timestamp when the user was created."))
    updated_at = models.DateTimeField(auto_now=True, help_text=_("Timestamp when the user was last updated."))

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    class Meta:
        db_table = "accounts_user"
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        indexes = [
            models.Index(fields=["email"], name="idx_accounts_user_email"),
            models.Index(fields=["username"], name="idx_accounts_user_username"),
        ]

    def __str__(self) -> str:
        return self.email

    def clean(self) -> None:
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    @property
    def full_name(self) -> str:
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()