from rest_framework import serializers

from .mixins import NestedCreateMixin, NestedUpdateMixin


class WritableNestedModelSerializer(NestedCreateMixin, NestedUpdateMixin,
                                     serializers.ModelSerializer):
    pass
