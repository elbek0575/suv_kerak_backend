# serializers.py
from rest_framework import serializers
from .models import AuditLog

class AuditLogSerializer(serializers.ModelSerializer):
    action_uz = serializers.CharField(source="get_action_display", read_only=True)
    class Meta:
        model  = AuditLog
        fields = ["ts","actor_id","action","action_uz","path","method","status","ip","meta"]
