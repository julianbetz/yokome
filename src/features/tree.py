#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Copyright 2019 Julian Betz
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#      http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from collections import OrderedDict
from collections.abc import Container, Iterable, Sized
import math
import json
from deprecated import deprecated

_TREE_SENTINEL = object()
"""Symbolic substitute for an unsupplied data value."""


class Tree(list):
    """A generic tree data structure."""

    def __init__(self):
        self._parent = None
        # Prevent instantiation of this base class
        if self.__class__ is Tree:
            raise NotImplementedError('The %s class is not instantiable'
                                      % (Tree.__name__,))
        super().__init__()

    def __setitem__(self, index, value):
        # For a Tree, insert before updating its parent data to ensure that the
        # parent data is not changed in case of a failure
        super().__setitem__(index, value)
        if isinstance(value, Tree):
            value.detach()
            value._parent = self
    
    def attach(self, value=_TREE_SENTINEL):
        child = (StructureTree()
                 if value is _TREE_SENTINEL
                 else DataTree(value))
        super().append(child)
        child._parent = self
        return child

    def detach(self):
        if self._parent is not None:
            found = False
            for i, sibling in enumerate(self._parent):
                if sibling is self:
                    found = True
                    break
            if not found:
                raise ValueError('Invalid parent for %s instance'
                                 % (Tree.__name__,))
            del self._parent[i]
            self._parent = None

    # TODO Use property instead
    def __invert__(self):
        return self._parent


class DataTree(Tree):
    """A tree structure with satellite data."""

    def __init__(self, value=None):
        self._data = value
        super().__init__()

    def __getitem__(self, index):
        return self._data if index is None else super().__getitem__(index)

    def __setitem__(self, index, value):
        if index is None:
            self._data = value
        else:
            super().__setitem__(index, value)
            
    def __repr__(self):
        return repr([self._data] + self)


class StructureTree(Tree):
    """A tree data structure without satellite data."""
    pass


@deprecated(reason='Superseded by LabeledTree')
class OrAndTree(DataTree):
    """A tree that disjunctively gathers AndOrTree children.

    Semantically, children of this node are alternatives.  They may only be
    instances of AndOrTree, i.e. they semantically represent cooccurrences.

    Nodes of this type may carry satellite data.
    """

    def __setitem__(self, index, value):
        if index is not None and not isinstance(value, AndOrTree):
            raise TypeError('Children of %s may only be instances of %s'
                            % (OrAndTree.__name__, AndOrTree.__name__))
        super().__setitem__(index, value)

    def attach(self, value=_TREE_SENTINEL):
        if value is not _TREE_SENTINEL:
            raise ValueError('Children of %s may not carry any satellite data'
                             % (OrAndTree.__name__))
        child = AndOrTree()
        super().append(child)
        child._parent = self
        return child


@deprecated(reason='Superseded by LabeledTree')
class AndOrTree(StructureTree):
    """A tree node that conjunctively gathers disjunctive children.

    Semantically, children of this node represent cooccurrences.  They may only
    be instances of OrAndTree, i.e. they semantically are alternatives.

    Nodes of this type do not carry any satellite data.
    """

    def __setitem__(self, index, value):
        if not isinstance(value, OrAndTree):
            raise TypeError('Children of %s may only be instances of %s'
                            % (AndOrTree.__name__, OrAndTree.__name__))
        super().__setitem__(index, value)

    def attach(self, value=_TREE_SENTINEL):
        if value is _TREE_SENTINEL:
            raise ValueError('Missing value for %s instance'
                             % (OrAndTree.__name__))
        child = OrAndTree(value)
        super().append(child)
        child._parent = self
        return child


class DataOnlyTree(DataTree):
    """A tree node that conjunctively gathers conjunctive children.

    Semantically, children of this node represent cooccurrences.  They may only
    be other instances of DataOnlyTree.
    
    Nodes of this type may carry satellite data.
    """

    def __setitem__(self, index, value):
        if index is not None and not isinstance(value, DataOnlyTree):
            raise TypeError('Children of %s may only be instances of %s'
                            % (DataOnlyTree.__name__, DataOnlyTree.__name__))
        super().__setitem__(index, value)

    def attach(self, value=_TREE_SENTINEL):
        if value is _TREE_SENTINEL:
            raise ValueError('Missing value for %s instance'
                             % (DataOnlyTree.__name__))
        child = DataOnlyTree(value)
        super().append(child)
        child._parent = self
        return child

    def _from_list(self, array):
        # Do not check via isinstance to prevent creation from a Tree instance
        if type(array) is not list and type(array) is not tuple:
            raise TypeError('Cannot create %s from non-list, non-tuple object'
                            % (DataOnlyTree.__name__))
        if len(array) < 1:
            raise ValueError('No data to create data node from empty list')
        self._data = array[0]
        for element in array[1:]:
            self.attach(None)._from_list(element)
        return self

    def from_list(array):
        return DataOnlyTree(None)._from_list(array)



class LabeledTree(Container, Iterable, Sized):
    def __init__(self, data=None):
        self._parent = None
        self._label = None
        self._data = data
        self._children = dict()


    @classmethod
    def _check_label_not_tuple(cls, label):
        """Prevent the use of tuples as labels for exclusive sets.
        
        Raise an error when attempting to use ``tuple`` objects.  Tuples are
        excluded from the data in order to prevent syntactic ambiguity when
        using bracket notation.

        :raises KeyError: If ``label`` is a ``tuple``
        """

        # Principle of least astonishment: Prevent misinterpretation of
        # e.g. tree[(a, b)] as tree[(a, b),] instead of tree[a, b]
        if isinstance(label, tuple):
            raise KeyError('%r objects are not supported as labels'
                           % (tuple.__name__,))


    @classmethod
    def _check_label_not_none(cls, label):
        """Prevent the use of ``None`` as label for exclusive sets.

        Raise an error when attempting to use ``None``.  ``None`` is reserved
        for accessing satellite data.  Child nodes cannot be accessed via this
        key.

        .. note::
        
            ``None`` is a valid way of access when it is not followed by any
            additional keys.  It then requests accessing satellite data.

        :raises KeyError: If ``label`` is ``None``
        """

        if label is None:
            raise KeyError('The %r key is reserved for satellite data' % None)


    @classmethod
    def _check_data(cls, data):
        """Prevent the insertion of invalid data into the tree.

        Raise errors when attempting to use ``slice`` objects or ``Ellipsis``.
        Slicing and arbitrary-length queries are currently not supported.

        :raises NotImplementedError: If ``data`` is a ``slice`` or ``Ellipsis``
        """

        if isinstance(data, slice):
            raise NotImplementedError('Slicing is currently not supported')
        if data is Ellipsis:
            raise NotImplementedError(
                'Use of %r is currently not supported' % Ellipsis)


    @classmethod
    def _check_child(cls, node):
        """Prevent the insertion of arbitrary objects in place of nodes.
        
        Raise an error when attempting to insert a child that is not an instance
        of ``LabeledTree``.

        :raises TypeError: If ``node`` is not an instance of ``LabeledTree``
        """

        if not isinstance(node, LabeledTree):
            raise TypeError('Children of %r may only be instances of %r'
                            % (cls.__name__, LabeledTree.__name__))


    def __contains__(self, x):
        """Whether the path through this tree is valid.

        ``x`` may be a tuple of labels alternating with data along a path in the
        tree, or a single label.  Alternatively, ``None`` can be used in place
        of the last or sole label to asks about the existence of non-``None``
        satellite data.

        :param x: path specification through the tree
        """
        return self._contains(x)


    def _contains(self, x):
        if isinstance(x, tuple):
            if len(x) == 0:
                return True
            elif len(x) == 1:
                x = x[0]
            else:
                self._check_data(x[1])
                self._check_data(x[0])
                self._check_label_not_tuple(x[0])
                self._check_label_not_none(x[0])
                # Do not use _getitem here to ensure that above checks are
                # not catched and interpreted as False
                try:
                    return (next(child for child in self._children[x[0]]
                                 if child._data == x[1])
                            ._contains(x[2:]))
                except (KeyError, StopIteration):
                    return False
        self._check_data(x)
        self._check_label_not_tuple(x)
        return (self._data is not None
                if x is None
                else self._children.__contains__(x))
    

    def __iter__(self):
        # Return an iterator over the children dictionary's items
        return ((label, list(iter(children)))
                for label, children in self._children.items())


    def __len__(self):
        # Return the number of keys in the children dictionary
        return len(self._children)


    # TODO Use property to set data instead of None value in __getitem__,
    # __setitem__ and __delitem__; allow None values in labels
    def __getitem__(self, key):
        """Get satellite data, a specific child or an iterator over children.

        ``key`` may be a tuple of labels alternating with data along a path in
        the tree, or a single label.  Alternatively, ``None`` can be used in
        place of the last or sole label.

        Depending on the last element of the path specification, return a list
        of children for a label, a child node for its data, or satellite data
        for ``None``, each at the end of the path, respectively.

        Return this node for the empty path.

        :param key: path specification through tree
        
        :rtype: satellite data, ``LabeledTree``, or an iterator over ``LabeledTree``s
        """
        return self._getitem(key)


    def _getitem(self, key):        
        if isinstance(key, tuple):
            if len(key) == 0:
                return self
            elif len(key) == 1:
                key = key[0]
            else:
                self._check_data(key[1])
                self._check_data(key[0])
                self._check_label_not_tuple(key[0])
                self._check_label_not_none(key[0])
                try:
                    return next(child for child in self._children[key[0]]
                                if child._data == key[1])._getitem(key[2:])
                except StopIteration:
                    raise KeyError(repr(key[1]))
        self._check_data(key)
        self._check_label_not_tuple(key)
        if key is None:
            return self._data
        return iter(self._children[key])


    def __setitem__(self, key, value):
        self._setitem(key, value)

    # TODO Handle empty tuple as key on root node
    def _setitem(self, key, value):
        """

        Children inserted under the same label are sorted in the order of last
        insertion.

        """
        if key is None:
            self._check_data(value)
            self._data = value
        elif isinstance(key, tuple):
            if len(key) == 0:
                parent = self._parent
                old_key = self._label
                self.detach()
                parent._setitem((old_key,), value)
            elif len(key) == 1:
                self._check_label_not_tuple(key[0])
                self._setitem(key[0], value)
            elif len(key) == 2:
                self._check_label_not_none(key[0])
                self._check_label_not_tuple(key[0])
                self._check_child(value)
                if key[1] == value._data:
                    self._setitem(key[0], value)
                else:
                    self._getitem(key)._setitem((), value)
            elif len(key) % 2 == 0:
                self._getitem(key[:-2])._setitem(key[-2:], value)
            else:
                self._getitem(key[:-1])._setitem(key[-1:], value)
        else:
            self._check_child(value)
            self._check_data(value._data)
            self._check_data(key)
            try:
                i, c = next((j, child)
                            for j, child in enumerate(self._children[key])
                            if child._data == value._data)
                del self._children[key][i]
                c._parent = None
                c._label = None
            except KeyError:
                self._children[key] = []
            except StopIteration:
                pass
            value.detach()
            self._children[key].append(value)
            value._parent = self
            value._label = key


    def __delitem__(self, key):
        """Delete satellite data, a specific child or all children for a label.

        ``key`` may be a tuple of labels alternating with data along a path in
        the tree, or a single label.  Alternatively, ``None`` can be used in
        place of the last or sole label.

        Depending on the last element of the path specification, remove all
        children along with their label for a label, a child node for its data,
        or satellite data for ``None``, each at the end of the path,
        respectively.

        Specifying the empty path is equivalent to calling :meth:`detach`.

        :param key: path specification through tree
        """
        self._delitem(key)


    def _delitem(self, key):
        if key is None:
            self._data = None
        elif isinstance(key, tuple):
            if len(key) == 0:
                self.detach()
            elif len(key) == 1:
                self._check_label_not_tuple(key[0])
                self._delitem(key[0])
            elif len(key) % 2 == 0:
                self._getitem(key)._delitem(())
            else:
                self._getitem(key[:-1])._delitem(key[-1:])
        else:
            self._check_data(key)
            for child in self._children[key]:
                child._parent = None
                child._label = None
            del self._children[key]


    def detach(self):
        """Break connection between this node and its parent."""
        
        if self._parent is not None:
            # Remove self from parent's children
            del self._parent._children[self._label][
                next(i for i, sibling
                     in enumerate(self._parent._children[self._label])
                     if sibling is self)]
            # Remove empty exclusive set from parent
            if not self._parent._children[self._label]:
                del self._parent._children[self._label]
            # Remove parent information from self
            self._parent = None
            self._label = None


    # TODO Use property instead
    def __invert__(self):
        return self._parent


    def __repr__(self):
        data_repr = repr(self._data) if self._data is not None else ''
        children_repr = (
            '{' + ', '.join(
                repr(label) + ': {' + ', '.join(
                    repr(child) for child in children) + '}'
                for label, children in self._children.items()) + '}'
            if self._children
            else '')
        return (self.__class__.__name__ + '('
                + data_repr + (', ' if data_repr and children_repr else '')
                + children_repr + ')')


    def __str__(self):
        return self._str()[:-1]


    def _str(self, prefix='', next_sibling=False, suppress_self=False):
        CYAN = '\033[36m'
        YELLOW = '\033[33m'
        PURPLE = '\033[35m'
        RED = '\033[31m'
        GREEN = '\033[32m'
        BLUE = '\033[34m'
        NO_COLOR = '\033[0m'
        out = ''
        if not suppress_self:
            out += (prefix
                    + ('\u251c' if next_sibling
                      else '\u2576' if prefix == ''
                      else '\u2570')
                    + '\u2574'
                    + (PURPLE + '*' if self._data is None
                      else (YELLOW + repr(self._data)))
                    + NO_COLOR + '\n')
        inner_prefix = prefix + ('\u2502 ' if next_sibling else '  ')
        l = len(self._children)
        for i, label in enumerate(self._children):
            k = len(self._children[label])
            if k == 1:
                out += (inner_prefix
                        + ('\u251c' if i < l - 1 else '\u2570')
                        + '\u2500\u2500\u2574'
                        + CYAN + repr(label) + NO_COLOR + ': '
                        + (PURPLE + '*' if self._children[label][0]._data is None
                           else (YELLOW + repr(self._children[label][0]._data)))
                        + NO_COLOR + '\n')
                suppress_self = True
            else:
                out += (inner_prefix
                        + ('\u251c' if i < l - 1 else '\u2570')
                        + '\u2500\u256e '
                        + CYAN + repr(label) + NO_COLOR + '\n')
                suppress_self = False
            for j, node in enumerate(self._children[label]):
                out += node._str(inner_prefix + ('\u2502 ' if i < l - 1
                                                 else '  '),
                                 j < k - 1,
                                 suppress_self)
                if j < k - 1 and (node._children or self._children[label][j + 1]._children):
                    out += (inner_prefix
                            + ('\u2502' if i < l - 1 else ' ')
                            + RED + '\u2576' + NO_COLOR + '\u2502'
                            + RED + '\u254c' * 6 + '\u2574' + NO_COLOR
                            + '\n')
            if i < l - 1:
                next_label_values = list(self._children.values())[i + 1]
                if (k > 1 or self._children[label][0]._children
                    or len(next_label_values) > 1
                    or next_label_values[0]._children):
                    out += (prefix
                            + ('\u2502' if next_sibling else ' ')
                            + GREEN + '\u2576' + NO_COLOR + '\u2502'
                            + GREEN + '\u2574 \u2576' + '\u254c' * 5
                            + '\u2574' + NO_COLOR + '\n')
        return out


    def to_dict(self):
        return {'data': self._data,
                'children': {label: [child.to_dict() for child in children]
                             for label, children in self._children.items()}}
        


class InvalidEntryError(Exception):
    def __init__(self, reason, *args, **kwargs):
        self.reason = reason
        super().__init__(*args, **kwargs)

        
class InvalidDataError(Exception):
    pass


class MissingDataException(Exception):
    pass



# TODO Document
class TemplateTree(LabeledTree):
    """Data is required to be hashable."""

    
    DEPTH = '_depth'
    PARENTS = 'parents'
    CHILDREN = '_children'
    LABEL = 'label'


    def __init__(self, data=None, restrictions=None):
        if isinstance(restrictions, str):
            with open(restrictions, 'r') as f:
                restrictions = json.load(f)
        if isinstance(restrictions, dict):
            self.prepare_restrictions(restrictions)
        elif restrictions is not None:
            raise TypeError('Could not parse %r' % (restrictions,))
        self._restrictions = restrictions
        super().__init__(data)


    def _restrictions_for(self, x):
        if self._restrictions is None:
            raise MissingDataException('No restrictions specified')
        try:
            restrictions = self._restrictions[x]
        except KeyError as e:
            raise InvalidEntryError(e, 'Restrictions for %r not found' % (x,))
        return restrictions

    
    def _label_for(self, x):
        restrictions = self._restrictions_for(x)
        try:
            label = restrictions[self.LABEL]
        except KeyError:
            raise InvalidDataError('%r missing in restrictions for %r'
                                   % (self.LABEL, x))
        return label


    def _depth_for(self, x):
        restrictions = self._restrictions_for(x)
        try:
            depth = restrictions[self.DEPTH]
        except KeyError:
            raise InvalidDataError('%r missing in restrictions for %r'
                                   % (self.DEPTH, x))
        return depth


    def _parents_for(self, x):
        restrictions = self._restrictions_for(x)
        try:
            parents = restrictions[self.PARENTS]
        except KeyError:
            raise InvalidDataError('%r missing in restrictions for %r'
                                   % (self.PARENTS, x))
        return parents


    def _default_parent_for(self, x):
        return self._parents_for(x)[0]


    @classmethod
    def _check_child(cls, node):
        """Prevent the insertion of arbitrary objects in place of nodes.
        
        Raise an error when attempting to insert a child that is not an instance
        of ``TemplateTree``.

        :raises TypeError: If ``node`` is not an instance of ``TemplateTree``
        """
        if not isinstance(node, TemplateTree):
            raise TypeError('Children of %r may only be instances of %r'
                            % (cls.__name__, TemplateTree.__name__))


    @classmethod
    def _prepare_restriction_depths(cls, pos_dict, pos, depth=0):
        """Check for cycles and non-equidistant paths from nodes to their descendants."""
        if pos_dict[pos][cls.DEPTH] is None:
            pos_dict[pos][cls.DEPTH] = depth
        else:
            assert pos_dict[pos][cls.DEPTH] == depth
        for child in pos_dict[pos][cls.CHILDREN]:
            cls._prepare_restriction_depths(pos_dict, child, depth + 1)


    # TODO Replace asserts with error raising
    # Idempotent
    @classmethod
    def prepare_restrictions(cls, pos_dict):
        assert isinstance(pos_dict, dict)
        root_data = SENTINEL = object()
        for data, restrictions in pos_dict.items():
            # TODO Verify whether adequate
            assert data is not Ellipsis and not isinstance(data, slice)
            assert isinstance(restrictions, dict)
            restrictions[cls.CHILDREN] = []
            restrictions[cls.DEPTH] = None
        for data, restrictions in pos_dict.items():
            assert cls.PARENTS in restrictions and isinstance(restrictions[cls.PARENTS], list)
            # Deduplicate parent list, but retain order; indirectly also enforce
            # deduplicated children lists
            restrictions[cls.PARENTS] = list(OrderedDict.fromkeys(restrictions[cls.PARENTS]))
            if not restrictions[cls.PARENTS]:
                assert root_data is SENTINEL # Ensure a unique root node
                root_data = data
            for parent in restrictions[cls.PARENTS]:
                assert parent in pos_dict, 'Missing key %r' % (parent,)
                parent_restrictions = pos_dict[parent]
                assert isinstance(parent_restrictions, dict)
                parent_restrictions[cls.CHILDREN].append(data)
        assert root_data is not SENTINEL # Ensure that there is a root node
        cls._prepare_restriction_depths(pos_dict, root_data)
        for data, restrictions in pos_dict.items():
            if restrictions[cls.DEPTH] is None:
                raise InvalidDataError('Node %r disconnected from root' % (data,))


    def __contains__(self, x):
        """Whether the path through this tree is valid.

        ``x`` must be child data along a path in the tree, or a single data
        object of an immediate child.  Labels are inferred based on the data
        restrictions.

        :param x: path specification through the tree

        """
        if not isinstance(x, tuple):
            x = (x,)
        try:
            x = tuple(f(y) for y in x for f in (self._label_for, lambda z: z))
        except InvalidEntryError:
            return False
        return super().__contains__(x)


    def __getitem__(self, key):
        """Get a specific child.

        ``key`` may be a tuple of data along a path in the tree, or a single
        data item.  Single items are interpreted as tuples of length one.
        Return the node at the end of the path; return this node for the empty
        path.

        :param key: path specification through tree
        
        :rtype: ``LabeledTree``

        """
        if not isinstance(key, tuple):
            key = (key,)
        key = tuple(f(y) for y in key for f in (self._label_for, lambda z: z))
        return super().__getitem__(key)


    # FIXME Check parent links in restrictions
    def __setitem__(self, key, value):
        # Unify input representations
        if not isinstance(key, tuple):
            key = (key,)
        # Test for inconsistent depths or labels of all descendants,
        # depth-first.  Test non-recursively to ensure that the tests are not
        # overridden by subclasses
        start_depth = self._depth_for(self._data) + len(key)
        nodes = [(value, start_depth, None)]
        while nodes:
            node, node_depth, node_label = nodes.pop()
            self._check_child(node)
            # Compare depth with restrictions
            data_depth = self._depth_for(node._data)
            if (data_depth != node_depth):
                raise InvalidEntryError(None, 'Expected depth of %r, got %r'
                                        % (node_depth, data_depth))
            # Compare stored labels with restrictions
            data_label = self._label_for(node._data)
            if node_depth > start_depth and (node_label != data_label
                                             or node._label != data_label):
                raise InvalidEntryError('Expected label %r, got %r and %r'
                                        % (data_label, node_label, node._label))
            for label, children in node._children.items():
                for child in children:
                    nodes.append((child, node_depth + 1, label))
        # Generate query path
        key = tuple(f(y) for y in key for f in (self._label_for, lambda z: z))
        # Insert the new subtree at its intended location
        super().__setitem__(key, value)
        # Update the new nodes' restriction information, depth-first
        nodes = [value]
        while nodes:
            node = nodes.pop()
            # No need to check validity, own restrictions are valid
            node._restrictions = self._restrictions
            for children in node._children.values():
                for child in children:
                    nodes.append(child)

    
    def __delitem__(self, key):
        """Delete a specific child.

        ``key`` may be a tuple of data along a path in the tree, or a single
        data item.  Single items are interpreted as tuples of length one.

        Remove the node at the end of the path.  Specifying the empty path is
        equivalent to calling :meth:`detach`.

        :param key: path specification through tree

        """
        if not isinstance(key, tuple):
            key = (key,)
        key = tuple(f(y) for y in key for f in (self._label_for, lambda z: z))
        super().__delitem__(key)


    def attach(self, data):
        child = self.__class__(data=data)
        self.__setitem__((data,), child)
        return child


    def _attach_nearby(self, pos):
        depth = self._depth_for(self._data)
        pos_depth = self._depth_for(pos)
        if pos_depth == 0:
            if self._parent is None:
                return self
            return self._parent._attach_nearby(pos)
        elif pos_depth <= depth:
            # Insert a POS tag above or next to the current node
            return self._parent._attach_nearby(pos)
        elif pos_depth == depth + 1:
            # Insert a POS tag at the level right below the current node
            if self._data not in self._parents_for(pos):
                # For valid restrictions, cannot move beyond the root node
                return self._parent._attach_nearby(self._default_parent_for(pos))._attach_nearby(pos)
            # Point of insertion found
            try:
                return self.__getitem__(pos)
                # Node exists already
            except KeyError:
                # Node has to be created
                return self.attach(pos)
        else:
            # Insert a POS tag at the level below, but not directly below the
            # current node
            return self._attach_nearby(self._default_parent_for(pos))._attach_nearby(pos)


    @classmethod
    def parse(cls, pos_list, pos_dict):
        if not isinstance(pos_dict, dict):
            raise InvalidDataError('Malformed restrictions')
        try:
            root_data = next(data
                             for data, restrictions in pos_dict.items()
                             if not restrictions[cls.PARENTS])
        except KeyError:
            raise InvalidDataError('%r missing in tag restrictions'
                                   % (cls.PARENTS,))
        except StopIteration:
            raise InvalidDataError('No root element found')
        # Implicitly check validity of restrictions
        pos_tree = cls(root_data, pos_dict)
        node = pos_tree
        for pos in pos_list:
            node = node._attach_nearby(pos)
        return pos_tree


    def is_valid_data(self, x):
        return x in self._restrictions


    def score(self, token):
        match_score, match_result = self._score(token)
        # Downscale the score along a quarter-circle curve in [0, 1] x [0, 1]
        return 1 - math.sqrt(1 - match_score ** 2), match_result


    # TODO Document
    def _score(self, token):
        """Evaluate how much the token specification in ``token`` matches this
        lexeme specification.

        The scoring function is as follows:

        .. math::

           \mathrm{score}(x, y) = \begin{cases}\frac{2 + \sum_{l \in \mathrm{labels}(x)} \max_{x^\prime \in \mathrm{children}(x, l), y^\prime \in \mathrm{children}(y)} \mathrm{score}(x^\prime, y^\prime)}{2 + \frac{\mathrm{length}(x) + \mathrm{length}(y)}{2}}, & \mathrm{data}(x) = \mathrm{data}(y)\\ 0, & \text{otherwise}\end{cases}

        This function has the following properties:

        * The score is in the interval [0, 1], with only a complete match scoring 1,
          and only an empty match scoring 0.  Trees that have their roots at
          different levels in the hierarchy receive a match score of 0.

        * Data in children nodes makes a contribution of at most half of the
          contribution of their parent nodes to the overall score.

        * Sibling nodes

        Nodes in unrelated parts of the hierarchy do not affect the score.  The
        same holds for overspecification: Descendant nodes in the token tree
        that are not found in the lexeme tree are not considered.

        In case of multiple inheritance, behavior on TemplateTree overrides
        behavior on DataOnlyTree.  A Resulting TemplateTree match contains the
        data from the input, but adheres to this TemplateTree's restrictions.

        """

        if (not isinstance(token, TemplateTree)
            and not isinstance(token, DataOnlyTree)):
            raise TypeError('Unable to match object of type %r'
                            % (type(token),))
        if self._data == token._data:
            subtree_score = 0
            if isinstance(token, TemplateTree):
                subtree_result = TemplateTree(token._data)
                # Point to own restrictions without revalidation
                subtree_result._restrictions = self._restrictions
            else:
                subtree_result = DataOnlyTree(token._data)
            # Pre-check input tags to decrease complexity of the matching loops.
            # Do not check parent validity, as this does not decrease
            # complexity.
            validate = (lambda x:
                        tuple(node for node in x
                              if self.is_valid_data(node._data)
                              and (self._depth_for(node._data)
                                   == self._depth_for(self._data) + 1)))
            if isinstance(token, DataOnlyTree):
                valid_token_nodes = validate(token)
            for label, children in self:
                if isinstance(token, TemplateTree):
                    if label not in token._children.keys():
                        continue
                    valid_token_nodes = validate(token._children[label])
                # Pre-check, see above
                label_token_nodes = tuple(node for node in valid_token_nodes
                                          if self._label_for(node._data)
                                          == label)
                # Match in the order given by the token POS tree
                children_score, children_result = 0, None
                for node in label_token_nodes:
                    node_score, node_result = 0, None
                    for child in children:
                        match_score, match_result = child._score(node)
                        if node_score < match_score:
                            node_score, node_result = match_score, match_result
                    if children_score < node_score:
                        children_score, children_result = (node_score,
                                                           node_result)
                subtree_score += children_score
                if children_result is not None:
                    if isinstance(subtree_result, TemplateTree):
                        # Validity checks in TemplateTree.__setitem__ are not
                        # necessary, and the label is already known
                        LabeledTree.__setitem__(subtree_result,
                                                 label,
                                                 children_result)
                    else:
                        subtree_result.append(children_result)
            return ((2 + subtree_score)
                    / (2 + 0.5 * (len(token._children.keys()
                                      if isinstance(token, TemplateTree)
                                      else token)
                                  + len(self._children.keys()))),
                    subtree_result)
        else:
            return 0, None


    # def _to_dict_no_restrictions(self):
    #     return {'data': self._data,
    #             'children': {label: [child._to_dict_no_restrictions()
    #                                  for child in children]
    #                          for label, children in self._children.items()}}
        

    # def to_dict(self):
    #     out = self._to_dict_no_restrictions()
    #     out['restrictions'] = self._restrictions
    #     return out


    def _from_dict(self, structure):
        for label, children in structure['children'].items():
            for child in children:
                # Insert child first, before inserting grandchildren into child,
                # to avoid low performance because of repeated restriction
                # checks
                required_label = self._label_for(child['data'])
                if required_label != label:
                    raise InvalidEntryError('Expected label %r, got %r'
                                            % (required_label, label))
                self.attach(child['data'])._from_dict(child)


    @classmethod
    def from_dict(cls, structure, restrictions):
        if not isinstance(structure, dict):
            raise TypeError('Cannot create %s instance from %r instance'
                            % (cls.__name__, type(structure)))
        root = cls(structure['data'], restrictions)
        root._from_dict(structure)
        return root
            
            

# TODO Extend to more general tree types
# TODO Move to classes
@deprecated
def dfs(tree, prefix='', next_sibling=False, shortened=False):
    if isinstance(tree, OrAndTree):
        if shortened:
            print(prefix[:-2] + ('\u2576' if prefix[:-2] == '' else '\u2570' if prefix[-2] == ' ' else '\u251c') + '\u2500\u2500\u2574' + ('\033[36m*' if tree[None] is None else ('\033[33m' + str(tree[None]))) + '\033[0m')
        else:
            print(prefix + ('\u251c' if next_sibling else '\u2576' if prefix == '' else '\u2570') + '\u2574' + ('\033[36m*' if tree[None] is None else ('\033[33m' + str(tree[None]))) + '\033[0m')
        l = len(tree)
        for i, node in enumerate(tree):
            dfs(node, prefix + ('\u2502 ' if next_sibling else '  '), i < l - 1)
            if i < l - 1:
                print(prefix + ('\u2502' if next_sibling else ' ') + '\033[31m\u2576\033[0m\u2502\033[31m\u254c\u254c\u254c\u254c\u254c\033[0m')
    elif isinstance(tree, AndOrTree):
        l = len(tree)
        if l == 0:
            print(prefix + ('\u2502' if next_sibling else '\u00b7' if prefix == '' else '\u2575'))
        elif l == 1:
            dfs(tree[0], prefix + ('\u2502 ' if next_sibling else '  '), False, True)
        else:
            print(prefix + ('\u251c' if next_sibling else '\u2576' if prefix == '' else '\u2570') + '\u2500\u256e')
            for i, node in enumerate(tree):
                dfs(node, prefix + ('\u2502 ' if next_sibling else '  '), i < l - 1)
    elif isinstance(tree, DataOnlyTree):
        print(prefix + ('\u251c' if next_sibling else '\u2576' if prefix == '' else '\u2570') + '\u2574' + ('\033[36m*' if tree[None] is None else ('\033[33m' + repr(tree[None]))) + '\033[0m')
        l = len(tree)
        for i, node in enumerate(tree):
            dfs(node, prefix + ('\u2502 ' if next_sibling else '  '), i < l - 1)
    else:
        raise TypeError('Attempted to traverse something that is not a valid %s'
                        % (Tree.__name__,))


# Tests
# ------------------------------------------------------------------------------

# Unit tests for Tree, DataTree and StructureTree

def unit_tests():
    def test_tree_not_instantiable():
        try:
            tree = Tree()
            return False
        except NotImplementedError:
            return True

    assert test_tree_not_instantiable(), 'Bare tree can be instantiated'

    tree = DataTree()
    assert tree._parent is None
    assert len(tree) == 0
    tree.attach()
    assert len(tree) == 1
    assert isinstance(tree[0], StructureTree)
    assert tree[0]._parent is ~tree[0]
    assert ~tree[0] is tree
    tree.attach(5)
    assert len(tree) == 2
    assert isinstance(tree[1], DataTree)
    assert tree[1]._parent is ~tree[1]
    assert ~tree[1] is tree
    assert tree[1] is tree[-1]
    assert tree[0] is tree[-2]
    tree._data = 5
    assert tree[None] == 5
    tree[None] = 6
    assert tree[None] == 6
    tree[1] = 11
    assert tree[1] == 11

    def test_structure_tree_set_data():
        try:
            tree[0][None] = 7
            return False
        except TypeError:
            return True

    def test_structure_tree_get_data():
        try:
            print(tree[0][None])
            return False
        except TypeError:
            return True

    assert test_structure_tree_set_data()
    assert test_structure_tree_get_data()

    tree = StructureTree()
    assert tree._parent is None
    assert len(tree) == 0
    tree.attach()
    assert len(tree) == 1
    assert isinstance(tree[0], StructureTree)
    tree.attach(5)
    assert len(tree) == 2
    assert isinstance(tree[1], DataTree)
    assert tree[1] is tree[-1]
    assert tree[0] is tree[-2]

    print('Unit tests \033[32msucceeded\033[0m')

# Output tests

def output_tests():
    pos_list = ['verb', 'godan', '', 'ra column', '', 'ichidan', '', '', '', 'intr. verb']
    pos_tree = OrAndTree()
    pos_tree.attach().attach('expression')\
            .attach().attach(pos_list[0])\
            .attach().attach(pos_list[1])\
            .attach().attach(pos_list[2])\
            .attach().attach(pos_list[3])\
            .attach().attach(pos_list[4])
    pos_tree[0][0][0][0].attach().attach(pos_list[5])\
                        .attach().attach(pos_list[6])\
                        .attach().attach(pos_list[7])\
                        .attach().attach(pos_list[8])
    pos_tree[0][0][0][0][0].attach(pos_list[9])
    pos_tree[0][0][0][0][1].attach(pos_list[9])
    verb_node = pos_tree[0][0][0][0]
    verb_node.attach()
    verb_node.attach()
    noun_node = pos_tree[0][0][0].attach('noun')
    noun_node.attach().attach('common')
    noun_node.attach().attach('proper')
    pos_tree.attach().attach('abbr.')

    and_list = DataOnlyTree()
    and_list.attach('verb').attach('godan').attach('').attach('r').attach('')
    and_list[0].attach('intr. verb')

    dfs(pos_tree)
    print()
    dfs(pos_tree[0])
    print()
    dfs(pos_tree[0][0][0])
    print()
    dfs(and_list)
    print()
    dfs(OrAndTree())
    print()
    dfs(OrAndTree(''))
    print()
    dfs(AndOrTree())
    print()
    dfs(DataOnlyTree())

if __name__ == '__main__':
    unit_tests()
    print()
    output_tests()
