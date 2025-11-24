from typing import TypeVar

from django.db.models import Model
from rest_framework import serializers

from .mixins import NestedCreateMixin, NestedUpdateMixin

_MT = TypeVar("_MT", bound=Model)

class WritableNestedModelSerializer(NestedCreateMixin[_MT], NestedUpdateMixin[_MT],
                                    serializers.ModelSerializer[_MT]):
    pass
