# -*- coding: utf-8 -*-
"""verschemes module

This module can be used to manage and enforce rules for version numbering.

"""

from __future__ import absolute_import
from __future__ import unicode_literals

import collections as _collections
import re as _re
from threading import RLock as _RLock

from future.builtins import map
from future.builtins import range
from future.builtins import zip
from future.utils import PY2 as _PY2

# custom future implementations for Python 2
if _PY2:  # pragma: no coverage  # pragma: no branch
    from verschemes.future.newstr import newstr as str
    from verschemes.future.newsuper import newsuper as super

from verschemes._version import __version__, __version_info__


DEFAULT_FIELD_TYPE = int
DEFAULT_SEGMENT_SEPARATOR = '.'


SegmentField = _collections.namedtuple('SegmentField',
                                       'type name re_pattern render')
"""The definition of an atomic portion of a version segment value.

This is an immutable set of metadata defining the parameters of a field in a
`SegmentDefinition`.

The attributes can be set only in the constructor by name or position and can
be accessed by attribute name (preferred) or item index:

0. :attr:`type` (default: `int`) is the underlying type of the field value.

   Only `int` and `str` have been tested.

1. :attr:`name` (default: "value") is the name of the field, which must be
   unique among all of the fields in a segment.

   Each segment will often have only one field, so the name is defaulted to
   something quite generic, but it must be explicitly set to ensure uniqueness
   when the `SegmentDefinition` contains multiple fields.

2. :attr:`re_pattern` (default: "0|[1-9][0-9]*") is the regular expression
   pattern that the string representation of the field value must match.

3. :attr:`render` (default: `str`) is the function that takes the underlying
   value and returns its appropriate string representation.

"""

SegmentField.__new__.__defaults__ = (DEFAULT_FIELD_TYPE, 'value',
                                     '0|[1-9][0-9]*', str)

DEFAULT_SEGMENT_FIELD = SegmentField()


_SegmentDefinition = _collections.namedtuple('_SegmentDefinition',
    'optional default separator fields name')

class SegmentDefinition(_SegmentDefinition):

    """The definition of a version segment.

    This is an immutable set of metadata defining the parameters of a segment.

    The attributes can be set only in the constructor by name or position and
    can be accessed by attribute name (preferred) or item index:

    0. :attr:`optional` (default: False) indicates whether the segment may be
       excluded from rendering and whether its value is allowed to be
       unspecified even if the segment has no default.

    1. :attr:`default` (default: None) is the implied value of the segment when
       the value is unspecified (or None).

    2. :attr:`separator` (default: '.') is the string within the version's
       string representation that comes just before the segment value(s).

       This value is ignored for the first segment in a version and also not
       rendered when all optional segments before it are unspecified.

    3. :attr:`fields` (default: a singular `SegmentField` instance) is the
       sequence of metadata for the field(s) in the segment.

    4. :attr:`name` (default: None) is an optional name for the segment.

       If the segment name is specified, it must be a valid Python identifier
       that does not start with an underscore.  This segment can then be
       identified by this name in the `Version` subclass in which it is used:

       a. The constructor and the `Version.replace` method will accept this
          name as a keyword argument, overriding the positional argument if
          also specified.
       b. There will be a read-only property to access this segment's value if
          the name is not already used in the class, so don't use a name that
          matches an existing attribute like 'render' if you want to use this
          property as an alternative to index access.

    """

    # This must be specified again to keep this subclass from making __dict__.
    __slots__ = ()

    def __new__(cls, optional=False, default=None,
                separator=DEFAULT_SEGMENT_SEPARATOR,
                fields=(DEFAULT_SEGMENT_FIELD,), name=None):
        """Provide default values.

        This cannot be done with `__init__` since `self` is immutable.

        """
        if isinstance(fields, SegmentField):
            fields = (fields,)
        elif (not isinstance(fields, tuple) and
              isinstance(fields, _collections.Iterable)):
            fields = tuple(fields)
        if not all(isinstance(x, SegmentField) for x in fields):
            raise ValueError(
                "Fields must be of type {}.".format(SegmentField))
        if len(set(x.name for x in fields)) < len(fields):
            raise ValueError(
                "Field names must be unique within a segment definition.")
        if default is not None:
            default = cls._validate_value(default, fields)
        if name:
            if name.startswith('_'):
                raise ValueError(
                    "Segment names must not begin with an underscore.")
            # For Python 2, name must be converted to str to have this method.
            # if not name.isidentifier():
            if not str(name).isidentifier():
                raise ValueError(
                    "Segment names must be valid identifiers.")
        return super().__new__(cls, bool(optional), default, str(separator),
                               fields, str(name) if name else None)

    @staticmethod
    def _validate_value(value, fields):
        if isinstance(value, str):
            value_string = value
        else:
            values = (list(value)
                      if isinstance(value, _collections.Iterable) else
                      [value])
            if len(values) > len(fields):
                raise ValueError(
                    "More values ({}) were given than fields ({}) in the "
                    "segment definition.  {}"
                    .format(len(values), len(fields), values))
            while len(values) < len(fields):
                values.append(None)
            value_string = "".join(x.render(None if y is None else x.type(y))
                                   for x, y in zip(fields, values))
        re_pattern = '^' + "".join('(?P<{}>{})'.format(x.name, x.re_pattern)
                                   for x in fields) + '$'
        match = _re.match(re_pattern, value_string)
        if not match:
            raise ValueError(
                "Version segment {!r} does not match {!r}."
                .format(value_string, re_pattern))
        result = [None if (match.group(fields[i].name) == "" and
                           fields[i].type is not str) else
                  fields[i].type(match.group(fields[i].name))
                  for i in range(len(fields))]
        return result[0] if len(fields) == 1 else tuple(result)

    @property
    def re_pattern(self):
        """The regular expression pattern for the segment's possible string
        representations.

        This is generated from the `~SegmentField.re_pattern`\s of its
        field(s).

        """
        return "".join('(?:{})'.format(x.re_pattern) for x in self.fields)

    @property
    def required(self):
        """Whether a value for this segment is required.

        It is required if it is not optional and has no default value.

        """
        return not self.optional and self.default is None

    def validate_value(self, value):
        """Validate the given value and return the value as the inner type.

        The given value may be a tuple of field values or a string that shall
        be parsed by the fields' regular expressions.

        """
        if value is None:
            if not self.optional and self.default is None:
                raise ValueError(
                    "A value is required because the version segment is not "
                    "optional and has no default.")
            return value
        return self._validate_value(value, self.fields)

    def render(self, value):
        """Return the given segment value as a string."""
        return (self.fields[0].render(value) if len(self.fields) == 1 else
                "".join(self.fields[i].render(value[i])
                        for i in range(len(self.fields))))

DEFAULT_SEGMENT_DEFINITION = SegmentDefinition()


class Version(tuple):

    """A class whose instances adhere to the version scheme it defines.

    The versioning rules are defined in `SEGMENT_DEFINITIONS`, which may be
    overridden in a subclass to make it more specific to the version scheme
    represented by the subclass.

    The concept is that the class represents a particular set of versioning
    rules (i.e., a version scheme), and the instances of that class are version
    identifiers that follow those rules.

    Pass the constructor either a version identifier as a `str` or the
    individual segment values in order corresponding to the
    `SEGMENT_DEFINITIONS` defined by the class (or any number of integers if
    using the default implementation).  Optional segments and segments with
    default values may be passed a value of `None` or excluded from the end.

    As of version 1.1, keyword arguments may also be given to the constructor
    when the keywords match the segments' names.  Any keyword arguments for
    segments also specified positionally will override the positional
    arguments.

    The instance's segment values can be accessed via standard indexing,
    slicing, and keys.  For example, ``instance[0]`` returns the value of the
    instance's first segment, ``instance[3:5]`` returns a tuple containing the
    values of the instance's fourth and fifth segments, and since version 1.1
    ``instance['name']`` returns the value of the segment with name 'name'.

    As of version 1.1, individual segment values can also be accessed via
    properties if the segment was given a name and the name does not conflict
    with an existing attribute of the class.

    The segment values acquired from indexing, slicing, keywords, and
    properties are cooked according to the segment definition (basically
    returning the default if the raw value is `None`).  The raw values can be
    accessed with :meth:`get_raw_item`.

    """

    SEGMENT_DEFINITIONS = ()
    """The parameters for segments in this version.

    If not using the default, this must be set to a sequence of
    `SegmentDefinition`\ s, one for each segment.  This should be done in the
    subclass definition and henceforth remain unmodified (hopefully the CAPs
    hinted at that).  If any changes *are* made after the class has been used,
    they won't be heeded anyway.

    The default (empty sequence) is special in that it allows for a varying and
    infinite number of segments, each following the rules of the default
    `SegmentDefinition`.  This means that the default implementation supports
    the most common versioning structure of an arbitrary number of integer
    segments separated by dots.

    """

    __class_cache = {}
    __class_cache_lock = _RLock()

    def __new__(cls, *args, **kwargs):
        segment_definitions = cls._get_definitions()
        if len(args) == 1 and isinstance(args[0], str):
            # Process a version string passed as the only argument.
            string = args[0]
            if segment_definitions:
                re = cls._get_re()
                match = re.match(string)
                if not match:
                    raise ValueError(
                        "Version string {!r} does not match {!r}."
                        .format(string, re.pattern))
                args = match.groups()
            else:
                args = string.split(DEFAULT_SEGMENT_SEPARATOR)
        else:
            # Validate the given args.
            args = list(args)
            if segment_definitions:
                if len(args) > len(segment_definitions):
                    raise ValueError(
                        "There are too many segment values ({}) for the "
                        "number of segment definitions ({})."
                        .format(len(args), len(segment_definitions)))
                while len(args) < len(segment_definitions):
                    args.append(None)
            elif not args:
                raise ValueError(
                    "One or more values are required when using implicit "
                    "segment definitions.")

        # Process `kwargs` into `args`.
        segment_indices = dict([(segment_definitions[i].name, i)
                                for i in range(len(segment_definitions))
                                if segment_definitions[i].name])
        for k, v in kwargs.items():
            if k not in segment_indices:
                raise KeyError(
                    "There is no segment with name {!r}."
                    .format(k))
            args[segment_indices[k]] = v

        # Validate and transform the values in `args`.
        args = [(segment_definitions[i] if segment_definitions else
                 DEFAULT_SEGMENT_DEFINITION).validate_value(args[i])
                for i in range(len(args))]

        # Instantiate, validate, and return the new object.
        result = super().__new__(cls, args)
        result.validate()
        return result

    # def __init__(self, *args, **kwargs):
    #     print("calling super.__init__")
    #     super().__init__()

    def __repr__(self):
        cls = type(self)
        return ("{}.{}(".format(cls.__module__, cls.__name__) +
                ", ".join(repr(x) for x in self) + ")")

    def __str__(self):
        return self.render()

    def __eq__(self, other):
        if not isinstance(other, Version):
            as_other = self._coerce_to_type(type(other))
            return False if as_other is None else (as_other == other)
        return self[:] == other[:]

    def __lt__(self, other):
        if not isinstance(other, Version):
            as_other = self._coerce_to_type(type(other))
            return NotImplemented if as_other is None else (as_other < other)
        return self[:] < other[:]

    def _coerce_to_type(self, type_):
        try:
            return type_(self)
        except (TypeError, ValueError):
            pass
        try:
            return type_(str(self))
        except (TypeError, ValueError):
            pass

    @classmethod
    def _get_definitions(cls):
        with cls.__class_cache_lock:
            cache = cls.__class_cache.setdefault(cls, {})
            result = cache.get('segment_definitions')
            if result is None:
                if not (isinstance(cls.SEGMENT_DEFINITIONS,
                                   _collections.Iterable) and
                        all(isinstance(x, SegmentDefinition)
                            for x in cls.SEGMENT_DEFINITIONS)):
                    raise TypeError(
                        "SEGMENT_DEFINITIONS for {} is not a sequence of "
                        "SegmentDefinitions."
                        .format(cls))
                names = [x.name for x in cls.SEGMENT_DEFINITIONS if x.name]
                if len(names) != len(set(names)):
                    raise ValueError(
                        "Segment names must be unique.")
                result = tuple(cls.SEGMENT_DEFINITIONS)
                # Add properties for segment names.
                for i, segment in enumerate(result):
                    name = segment.name
                    if not name or name in dir(cls):
                        # no name or already defined
                        continue
                    setattr(cls, name, property(lambda o, i=i: o[i]))
                cache['segment_definitions'] = result
        return result

    @classmethod
    def _get_re(cls):
        with cls.__class_cache_lock:
            cache = cls.__class_cache.setdefault(cls, {})
            result = cache.get('re')
            if result is None:
                definitions = cls._get_definitions()
                re = ""
                for i in range(len(definitions)):
                    d = definitions[i]
                    re_segment = ""
                    if i > 0:
                        re_segment += "(?:" + _re.escape(d.separator) + ")"
                        if all(not x.required for x in definitions[:i]):
                            re_segment += "?"
                    re_segment += "(?P<segment{}>{})".format(i, d.re_pattern)
                    if not d.required:
                        re_segment = "(?:" + re_segment + ")?"
                    re += re_segment
                cache['re'] = result = _re.compile('^' + re + '$')
        return result

    def _get_segment_definition(self, item=None):
        definitions = self._get_definitions()
        if definitions:
            if item is not None:
                if isinstance(item, str):
                    definitions = dict((x.name, x) for x in definitions
                                       if x.name)
                definitions = definitions[item]
            return definitions
        return ((DEFAULT_SEGMENT_DEFINITION,) * len(self.get_raw_item(item))
                if item is None or isinstance(item, slice) else
                DEFAULT_SEGMENT_DEFINITION)

    def get_raw_item(self, item=None):
        """Return the raw segment value (or values if `item` is a slice).

        This is an alternative to :meth:`~object.__getitem__` (i.e., bracket
        item retrieval) and named-segment properties, which cook the value(s)
        according to their segment definition(s).

        """
        if item is None:
            item = slice(0, len(self))
        if isinstance(item, str):
            for index, definition in enumerate(self._get_definitions()):
                if definition.name == item:
                    item = index
                    break
            if isinstance(item, str):
                raise KeyError(item)
        return super().__getitem__(item)

    def __getitem__(self, item):
        def get(v, d):
            return v if v is not None else d.default
        definition = self._get_segment_definition(item)
        value = self.get_raw_item(item)
        return (tuple(map(get, value, definition))
                if isinstance(item, slice) else
                get(value, definition))

    if _PY2:  # pragma: no coverage  # pragma: no branch
        def __getslice__(self, i, j):
            return self.__getitem__(slice(i, j))

    def _render_exclude_defaults_callback(self, index, scope=None):
        if scope is None:
            scope = range(len(self))
        if index in scope:
            if any(self.get_raw_item(i) is not None
                   for i in range(index, max(scope) + 1)):
                return False
        return (self._get_segment_definition(index).optional and
                self.get_raw_item(index) is None)

    def render(self, exclude_defaults=True, include_callbacks=(),
               exclude_callbacks=()):
        """Render the version into a string representation.

        Pass `False` (or equivalent) for the `exclude_defaults` argument to
        stop the default behavior of excluding optional segments that have a
        default value but have not been explicitly set.

        If there was only one way to render a version, then this method would
        not exist, and its implementation would be in `__str__`.  There is,
        however, only one default way, which is done when `__str__` is called,
        and that is to call this method with its default arguments.

        There could be many ways to render a version, depending on its
        complexity and features.  The base class implements rendering with
        only one simple argument (`exclude_defaults`) and two complex arguments
        (`include_callbacks` and `exclude_callbacks`).  The two complex
        arguments (i.e., callback arguments) allow for future versions and
        subclasses to provide additional simple arguments.  (Keep reading if
        this interests you.)

        The signature of this method should be considered the most volatile in
        the project.  The callback arguments should never be passed by position
        to keep the code prepared for injection of additional simple arguments
        in the base implementation that are more likely to be passed by
        position.

        **Callback structure**

        The callback arguments are sequences of metadata describing how the
        simple arguments are processed.  The metadata may just be a function
        or a sequence consisting of a function and any additional arguments.
        Each callback function requires the 'version' (or 'self' if its a
        method) argument and the 'index' argument.  The "additional" arguments
        mentioned above follow the required arguments in the callback
        function's signature.

        **Callback processing**

        The functions in `include_callbacks` can return `True` (or equivalent)
        to force the segment identified by the 'index' argument to be included
        in the rendering.  If no "include" callbacks force the inclusion of the
        segment, then the functions in `exclude_callbacks` can return `True`
        (or equivalent) to exclude the segment of the version identified by the
        'index' argument in the rendering.  Any segment with a value (i.e., not
        `None`) that is not excluded by this process will be rendered in the
        result.  The `exclude_defaults` argument is an example of a simple
        argument whose affect is implemented via `exclude_callbacks` with the
        `_render_exclude_defaults_callback` method.

        """
        include_callbacks = list(include_callbacks)
        exclude_callbacks = list(exclude_callbacks)
        if exclude_defaults:
            exclude_callbacks.append(
                type(self)._render_exclude_defaults_callback)

        def callback_affirmative(callback, index):
            args = [self, index]
            if (not isinstance(callback, _collections.Callable) and
                isinstance(callback, _collections.Iterable)):
                args.extend(callback[1:])
                callback = callback[0]
            return callback(*args)

        result = ""
        definitions = self._get_segment_definition()
        for i in range(len(self)):
            definition = definitions[i]
            value = self[i]
            if definition.optional and value is None:
                continue
            include = False
            for callback in include_callbacks:
                if callback_affirmative(callback, i):
                    include = True
            if not include:
                include = True
                for callback in exclude_callbacks:
                    if callback_affirmative(callback, i):
                        include = False
            if not include:
                continue
            if len(result) > 0:
                result += definition.separator
            result += definition.render(value)
        return result

    def replace(self, **kwargs):
        """Return a copy of this version with the given segments replaced.

        Each keyword argument can either be an underscore ('_') followed by the
        numeric segment index or the segment name.  Each identified segment is
        replaced with the argument's value.  Segment name arguments take
        precedence over underscore-index arguments.

        """
        values = list(self.get_raw_item())
        for k in list(kwargs):
            if k.startswith('_') and k[1:].isdigit():
                values[int(k[1:])] = kwargs.pop(k)
        return type(self)(*values, **kwargs)

    def validate(self):
        """Override this in subclasses that require intersegment validation.

        Raise an appropriate exception if validation fails.

        """