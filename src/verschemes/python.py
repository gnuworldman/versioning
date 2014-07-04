# -*- coding: utf-8 -*-
"""verschemes.python module

The Python versioning module implements standard
`Python <https://www.python.org/>`_
`versioning <https://docs.python.org/3/faq/general.html#how-does-the-python-version-numbering-scheme-work>`__.

"""

from verschemes import SegmentDefinition as _SegmentDefinition
from verschemes import SegmentField as _SegmentField
from verschemes import Version as _Version


SEGMENTS = (MAJOR, MINOR, MICRO, SUFFIX) = range(4)


class PythonMajorVersion(_Version):

    """A major Python version.

    This version scheme has one segment that identifies the major Python
    version, which is only incremented for really major changes in the
    language.  It is the base for the more detailed Python version classes and
    is mostly only useful itself for comparison.  For example:

    >>> python2 = PythonMajorVersion(2)
    >>> my_python_version = PythonVersion('2.7.1')
    >>> assert(my_python_version.major_version == python2)

    """

    SEGMENT_DEFINITIONS = (
        _SegmentDefinition(),
    )

    @property
    def major_version(self):
        """Return a new `PythonMajorVersion` with the object's values.

        This is mainly useful in subclasses.

        """
        return PythonMajorVersion(self[MAJOR])


class PythonMinorVersion(PythonMajorVersion):

    """A minor Python version.

    This version scheme has two segments that identify the minor Python
    version, which is incremented for less earth-shattering changes in the
    language than a major version increment.  It is the base for the more
    detailed Python version classes and is mostly only useful itself for
    comparison.  For example:

    >>> python33 = PythonMinorVersion(3, 3)
    >>> my_python_version = PythonVersion(3, 4, 2)
    >>> assert(my_python_version.minor_version > python33)

    """

    SEGMENT_DEFINITIONS = PythonMajorVersion.SEGMENT_DEFINITIONS + (
        _SegmentDefinition(),
    )

    @property
    def minor_version(self):
        """Return a new `PythonMinorVersion` with the object's values.

        This is mainly useful in subclasses.

        """
        return PythonMinorVersion(self[MAJOR], self[MINOR])


class PythonMicroVersion(PythonMinorVersion):

    """A micro Python version.

    This version scheme has three segments that identify the micro Python
    version, which is incremented for each bugfix release (see `PEP 6
    <http://legacy.python.org/dev/peps/pep-0006/>`_).  It is the base for the
    more detailed Python version classes and is mostly only useful itself for
    comparison.  For example:

    >>> python301 = PythonMicroVersion(3, 0, 1)
    >>> my_python_version = PythonVersion(3, 0, 1, ('b', 1))
    >>> assert(my_python_version.micro_version == python301)

    """

    SEGMENT_DEFINITIONS = PythonMinorVersion.SEGMENT_DEFINITIONS + (
        _SegmentDefinition(
            optional=True
        ),
    )

    @property
    def micro_version(self):
        """Return a new `PythonMicroVersion` with the object's values.

        This is mainly useful in subclasses.

        """
        return PythonMicroVersion(self[MAJOR], self[MINOR], self[MICRO])


class PythonVersion(PythonMicroVersion):

    """A complete, specific Python version.

    This version scheme has four segments that identify a specific version of
    Python.  See the link in the module documentation for details about the
    Python version scheme.

    """

    SEGMENT_DEFINITIONS = PythonMicroVersion.SEGMENT_DEFINITIONS + (
        _SegmentDefinition(
            optional=True,
            separator='',
            fields=(
                _SegmentField(
                    type=str,
                    name='releaselevel',
                    re_pattern='[+abc]',
                ),
                _SegmentField(
                    name='serial',
                    re_pattern='(?<=[+])|(?<![+])(?:0|[1-9][0-9]*)',
                    render=lambda x: "" if x is None else str(x),
                ),
            ),
        ),
    )

    @property
    def is_nondevelopment(self):
        """Whether this version represents a non-development release.

        This simply says whether it is equivalent to its `micro_version`; that
        is, whether the `SUFFIX`-index value is `None`.

        >>> assert(PythonVersion('3.4.1').is_nondevelopment)
        >>> assert(not PythonVersion('3.4.1c1').is_nondevelopment)
        >>> assert(not PythonVersion('3.4.1+').is_nondevelopment)

        """
        return self[SUFFIX] is None

    @property
    def is_release(self):
        """Whether this version represents a release.

        This simply says whether the `SUFFIX`-index value is not '+'.  A '+'
        indicates that it is an unreleased version, built directly from the
        Subversion trunk; anything else is a release (be it development or
        non-development).

        >>> assert(PythonVersion('3.4.1').is_release)
        >>> assert(PythonVersion('3.4.1c1').is_release)
        >>> assert(not PythonVersion('3.4.1+').is_release)

        """
        return self[SUFFIX] != ('+', None)
