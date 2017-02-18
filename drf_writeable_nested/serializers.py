from rest_framework import serializers

from .mixins import NestedCreateMixin, NestedUpdateMixin


class WriteableNestedModelSerializer(NestedCreateMixin, NestedUpdateMixin,
                                     serializers.ModelSerializer):
    pass
