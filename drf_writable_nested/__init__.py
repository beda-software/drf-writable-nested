__title__ = 'DRF writable nested'
__version__ = '0.5.2'
__author__ = 'beda.software'
__license__ = 'BSD 2-Clause'
__copyright__ = 'Copyright 2014-2018 beda.software'

# Version synonym
VERSION = __version__

from django.core.exceptions import AppRegistryNotReady
import warnings

try:
    from .mixins import NestedUpdateMixin, NestedCreateMixin, UniqueFieldsMixin
    from .serializers import WritableNestedModelSerializer
except AppRegistryNotReady as e:
    warnings.warn("AppRegistryNotReady raised and catched", RuntimeWarning)
