# -*- coding: utf-8 -*-
'''
Création : Aug 27th, 2015

@author: Eric Lapouyade
'''

import os

__all__ = ['PerfData']

import re

class PerfData(object):
    def __init__(self, label, value, uom=None, warn=None, crit=None, minval=None, maxval=None):
        self.label = label
        self.value = value
        self.uom = uom
        self.warn = warn
        self.crit = crit
        self.minval = minval
        self.maxval = maxval

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if value is None:
            raise ValueError("value must not be None")
        elif not self._is_valid_value(value):
            raise ValueError("value must be in class [-0-9.]")

        self._value = value

    @property
    def minval(self):
        return self._minval

    @minval.setter
    def minval(self, value):
        if not self._is_valid_value(value):
            raise ValueError("minval must be in class [-0-9.]")

        self._minval = value

    @property
    def maxval(self):
        return self._maxval

    @maxval.setter
    def maxval(self, value):
        if not self._is_valid_value(value):
            raise ValueError("maxval must be in class [-0-9.]")

        self._maxval = value

    @property
    def uom(self):
        return self._uom

    @uom.setter
    def uom(self, value):
        valids = ['', 's', '%', 'b', 'kb', 'mb', 'gb', 'tb', 'c']
        if value is not None and not str(value).lower() in valids:
            raise ValueError("uom must be in: %s" % valids)

        self._uom = value


    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,self)

    def __str__(self):
        """
            Perf data looks like this :
            'label'=value[UOM];[warn];[crit];[min];[max]
        """
        # Quotify the label
        label = self._quote_if_needed(self.label)

        # Check for None in each and make it empty string if so
        uom = self.uom or ''
        warn = self.warn or ''
        crit = self.crit or ''
        minval = self.minval or ''
        maxval = self.maxval or ''

        # Create the proper format and return it
        return "%s=%s%s;%s;%s;%s;%s" % (label, self.value, uom, warn, crit, minval, maxval)

    def _is_valid_value(self, value):
        value_format = re.compile(r"[-0-9.]+$")
        return value is None or value_format.match(str(value))

    def _quote_if_needed(self, value):
        if '=' in value or ' ' in value or "'" in value:
            # Quote the string and replace single quotes with double single
            # quotes and return that
            return "'%s'" % value.replace("'", "''")
        else:
            return value
