__title__ = 'DRF writable nested'
__version__ = '0.4.1'
__author__ = 'beda.software'
__license__ = 'BSD 2-Clause'
__copyright__ = 'Copyright 2014-2018 beda.software'

# Version synonym
VERSION = __version__


from .mixins import NestedUpdateMixin, NestedCreateMixin
from .serializers import WritableNestedModelSerializer
