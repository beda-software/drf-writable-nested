__title__ = 'DRF writable nested'
__version__ = '0.0.3'
__author__ = 'Bro.engineering'
__license__ = 'BSD 2-Clause'
__copyright__ = 'Copyright 2014-2017 Bro.engineering'

# Version synonym
VERSION = __version__


from .mixins import NestedUpdateMixin, NestedCreateMixin, SavePriorityMixin
from .serializers import WritableNestedModelSerializer
