"""
Serializers for BIST Companies and User Comments.
Includes strict length bounds and input sanitization (Code Guardian Phase 2).
"""

import html
from rest_framework import serializers
from .models import Comment, Company


class CompanyListSerializer(serializers.ModelSerializer):
    comment_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Company
        fields = (
            "id",
            "code",
            "name",
            "sector",
            "indices",
            "kap_url",
            "is_bist30",
            "comment_count",
            "updated_at",
        )


class CommentSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="user.username", read_only=True)
    company_code = serializers.SlugRelatedField(
        source="company",
        slug_field="code",
        queryset=Company.objects.all(),
    )
    company_name = serializers.CharField(source="company.name", read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = (
            "id",
            "author_username",
            "company_code",
            "company_name",
            "target_type",
            "statement_type",
            "period",
            "content",
            "is_edited",
            "is_owner",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "author_username",
            "company_name",
            "is_edited",
            "is_owner",
            "created_at",
            "updated_at",
        )

    def get_is_owner(self, obj: Comment) -> bool:
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return False
        return obj.user_id == request.user.id

    def validate_content(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise serializers.ValidationError(
                "Yorum metni en az 3 karakter olmalıdır."
            )
        if len(cleaned) > 2000:
            raise serializers.ValidationError(
                "Yorum metni en fazla 2000 karakter olabilir."
            )
        # Strip control characters while keeping plain text safe
        cleaned = "".join(ch for ch in cleaned if ch == "\n" or ch == "\t" or ord(ch) >= 32)
        return cleaned

    def validate_period(self, value: str) -> str:
        cleaned = value.strip()[:32]
        return html.escape(cleaned)

    def update(self, instance: Comment, validated_data: dict) -> Comment:
        if "content" in validated_data and validated_data["content"] != instance.content:
            instance.content = validated_data["content"]
            instance.is_edited = True
            instance.save(update_fields=["content", "is_edited", "updated_at"])
        return instance
