# sqlalchemy/naming.py
# Copyright (C) 2005-2019 the SQLAlchemy authors and contributors
# <see AUTHORS file>
#
# This module is part of SQLAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

"""Establish constraint and index naming conventions.


"""

import re

from .elements import _defer_name
from .elements import _defer_none_name
from .elements import conv
from .schema import CheckConstraint
from .schema import Column
from .schema import Constraint
from .schema import ForeignKeyConstraint
from .schema import Index
from .schema import PrimaryKeyConstraint
from .schema import Table
from .schema import UniqueConstraint
from .. import event
from .. import events  # noqa
from .. import exc


class ConventionDict(object):
    def __init__(self, const, table, convention):
        self.const = const
        self._is_fk = isinstance(const, ForeignKeyConstraint)
        self.table = table
        self.convention = convention
        self._const_name = const.name

    def _debug_info(self):
        # used to generate a better exception message for debugging
        _debug_msg = 'Constraint Identifiers: '
        try:
            _debug_msg += "Table- `%s`;" % self.const.table.name
            _columns = ["`%s`" % i.name for i in self.const.columns]
            _debug_msg += " Column(s)- %s." % ", ".join(_columns)
        except:
            pass
        return _debug_msg

    def _key_table_name(self):
        return self.table.name

    def _column_X(self, idx):
        if self._is_fk:
            fk = self.const.elements[idx]
            return fk.parent
        else:
            if not self.const.columns:
                raise exc.InvalidRequestError(
                    "Naming convention requires column %s for a constraint, "
                    "however the constraint does not have that number of "
                    "columns. " % idx + self._debug_info()
                )
            return list(self.const.columns)[idx]

    def _key_constraint_name(self):
        if isinstance(self._const_name, (type(None), _defer_none_name)):
            raise exc.InvalidRequestError(
                "Naming convention including "
                "%(constraint_name)s token requires that "
                "constraint is explicitly named. " + self._debug_info()
            )
        if not isinstance(self._const_name, conv):
            self.const.name = None
        return self._const_name

    def _key_column_X_key(self, idx):
        # note this method was missing before
        # [ticket:3989], meaning tokens like ``%(column_0_key)s`` weren't
        # working even though documented.
        return self._column_X(idx).key

    def _key_column_X_name(self, idx):
        return self._column_X(idx).name

    def _key_column_X_label(self, idx):
        return self._column_X(idx)._label

    def _key_referred_table_name(self):
        fk = self.const.elements[0]
        refs = fk.target_fullname.split(".")
        if len(refs) == 3:
            refschema, reftable, refcol = refs
        else:
            reftable, refcol = refs
        return reftable

    def _key_referred_column_X_name(self, idx):
        fk = self.const.elements[idx]
        # note that before [ticket:3989], this method was returning
        # the specification for the :class:`.ForeignKey` itself, which normally
        # would be using the ``.key`` of the column, not the name.
        return fk.column.name

    def __getitem__(self, key):
        if key in self.convention:
            return self.convention[key](self.const, self.table)
        elif hasattr(self, "_key_%s" % key):
            return getattr(self, "_key_%s" % key)()
        else:
            col_template = re.match(r".*_?column_(\d+)(_?N)?_.+", key)
            if col_template:
                idx = col_template.group(1)
                multiples = col_template.group(2)

                if multiples:
                    if self._is_fk:
                        elems = self.const.elements
                    else:
                        elems = list(self.const.columns)
                    tokens = []
                    for idx, elem in enumerate(elems):
                        attr = "_key_" + key.replace("0" + multiples, "X")
                        try:
                            tokens.append(getattr(self, attr)(idx))
                        except AttributeError:
                            raise KeyError(key)
                    sep = "_" if multiples.startswith("_") else ""
                    return sep.join(tokens)
                else:
                    attr = "_key_" + key.replace(idx, "X")
                    idx = int(idx)
                    if hasattr(self, attr):
                        return getattr(self, attr)(idx)
        raise KeyError(key)


# NOTE: "base" prefixes might be augmented by `_get_prefixes()`
_base_prefix_dict = {
    Index: "ix",
    PrimaryKeyConstraint: "pk",
    CheckConstraint: "ck",
    UniqueConstraint: "uq",
    ForeignKeyConstraint: "fk",
}


def _get_prefixes(const):
    """
    `_get_prefixes(const)` allows for a `_base_prefix` dict item to be augmented
    in certain use-cases.

    * `_type_bound` constraints, which are automatically created for Bool/Enum
      validation on certain backends will prefer a `type_ck` prefix
    """
    for super_ in type(const).__mro__:
        if super_ in _base_prefix_dict:
            prefix = _base_prefix_dict[super_]
            if isinstance(const, Constraint) and const._type_bound:
                if isinstance(const.name, _defer_none_name):
                    # only use the `type_` prefix if no name was presented
                    yield "type_%s" % prefix, super_
            yield prefix, super_


def _get_convention(dict_, const):
    for prefix, super_ in _get_prefixes(const):
        if prefix in dict_:
            return dict_[prefix]
        elif super_ in dict_:
            return dict_[super_]
    else:
        return None


def _constraint_name_for_table(const, table):
    metadata = table.metadata
    convention = _get_convention(metadata.naming_convention, const)

    if isinstance(const.name, conv):
        return const.name
    elif (
        convention is not None
        and not isinstance(const.name, conv)
        and (
            const.name is None
            or "constraint_name" in convention
            or isinstance(const.name, _defer_name)
        )
    ):
        return conv(
            convention
            % ConventionDict(const, table, metadata.naming_convention)
        )
    elif isinstance(convention, _defer_none_name):
        return None


@event.listens_for(Constraint, "after_parent_attach")
@event.listens_for(Index, "after_parent_attach")
def _constraint_name(const, table):
    if isinstance(table, Column):
        # for column-attached constraint, set another event
        # to link the column attached to the table as this constraint
        # associated with the table.
        event.listen(
            table,
            "after_parent_attach",
            lambda col, table: _constraint_name(const, table),
        )
    elif isinstance(table, Table):
        if isinstance(const.name, (conv, _defer_name)):
            return

        newname = _constraint_name_for_table(const, table)
        if newname is not None:
            const.name = newname
