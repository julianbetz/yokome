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


from collections.abc import Container, Iterable, Sized
import json


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

    def __invert__(self):
        return self._parent


class DataTree(Tree):
    """A tree structure with satellite data."""

    def __init__(self, value=None):
        self.data = value
        super().__init__()

    def __getitem__(self, index):
        return self.data if index is None else super().__getitem__(index)

    def __setitem__(self, index, value):
        if index is None:
            self.data = value
        else:
            super().__setitem__(index, value)
            
    def __repr__(self):
        return repr([self.data] + self)


class StructureTree(Tree):
    """A tree data structure without satellite data."""
    pass


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
        self.data = array[0]
        for element in array[1:]:
            self.attach(None)._from_list(element)
        return self

    def from_list(array):
        return DataOnlyTree(None)._from_list(array)



class POSTree(Container, Iterable, Sized):
    def __init__(self, data=None):
        self._parent = None
        self._key = None
        self._data = data
        self._children = dict()


    @classmethod
    def _check_key_not_tuple(cls, key):
        """Prevent the use of tuples as keys for exclusive sets.
        
        Raise an error when attempting to use ``tuple`` objects.  Tuples are
        excluded from the data in order to prevent syntactic ambiguity when
        using bracket notation.

        :raises KeyError: If ``key`` is a ``tuple``
        """

        # Principle of least astonishment: Prevent misinterpretation of
        # e.g. tree[(a, b)] as tree[(a, b),] instead of tree[a, b]
        if isinstance(key, tuple):
            raise KeyError('%r objects are not supported as keys'
                           % (tuple.__name__,))


    @classmethod
    def _check_key_not_none(cls, key):
        """Prevent the use of ``None`` as key for exclusive sets.

        Raise an error when attempting to use ``None``.  ``None`` is reserved
        for accessing satellite data.  Child nodes cannot be accessed via this
        key.

        .. note::
        
            ``None`` is a valid way of access when it is not followed by any
            additional keys.  It then requests accessing satellite data.

        :raises KeyError: If ``key`` is ``None``
        """

        if key is None:
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
        of ``POSTree``.

        :raises TypeError: If ``node`` is not an instance of ``POSTree``
        """

        if not isinstance(node, POSTree):
            raise TypeError('Children of %r may only be instances of %r'
                            % (cls.__name__, POSTree.__name__))


    def __contains__(self, x):
        """Whether the path through this tree is valid.

        ``x`` may be a tuple of labels alternating with data along a path in the
        tree, or a single label.  Alternatively, ``None`` can be used in place
        of the last or sole label to asks about the existence of non-``None``
        satellite data.

        :param x: path specification through the tree
        """

        if isinstance(x, tuple):
            if len(x) == 0:
                return True
            elif len(x) == 1:
                x = x[0]
            else:
                self._check_data(x[1])
                self._check_data(x[0])
                self._check_key_not_tuple(x[0])
                self._check_key_not_none(x[0])
                # Do not use __getitem__ here to ensure that above checks are
                # not catched and interpreted as False
                try:
                    return (next(child for child in self._children[x[0]]
                                 if child._data == x[1])
                            .__contains__(x[2:]))
                except (KeyError, StopIteration):
                    return False
        self._check_data(x)
        self._check_key_not_tuple(x)
        return (self._data is not None
                if x is None
                else self._children.__contains__(x))
    

    def __iter__(self):
        # Return an iterator over the children dictionary's keys
        return iter(self._children)


    def __len__(self):
        # Return the number of keys in the children dictionary
        return len(self._children)


    def __getitem__(self, key):
        """Get satellite data, a specific child or an iterator over children.

        ``key`` may be a tuple of labels alternating with data along a path in
        the tree, or a single label.  Alternatively, ``None`` can be used in
        place of the last or sole label.

        Depending on the last element of the path specification, return a list
        of children for a label, a child node for its data, or satellite data
        for ``None``, each at the end of the path, respectively.

        Returns this node for the empty path.

        :param key: path specification through tree
        
        :rtype: satellite data, ``POSTree``, or an iterator over ``POSTree``s
        """
        
        if isinstance(key, tuple):
            if len(key) == 0:
                return self
            elif len(key) == 1:
                key = key[0]
            else:
                self._check_data(key[1])
                self._check_data(key[0])
                self._check_key_not_tuple(key[0])
                self._check_key_not_none(key[0])
                try:
                    return next(child for child in self._children[key[0]]
                                if child._data == key[1]).__getitem__(key[2:])
                except StopIteration:
                    raise KeyError(repr(key[1]))
        self._check_data(key)
        self._check_key_not_tuple(key)
        if key is None:
            return self._data
        return iter(self._children[key])


    def __setitem__(self, key, value):
        if key is None:
            self._check_data(value)
            self._data = value
        elif isinstance(key, tuple):
            if len(key) == 0:
                parent = self._parent
                old_key = self._key
                self.detach()
                parent.__setitem__((old_key,), value)
            elif len(key) == 1:
                self._check_key_not_tuple(key[0])
                self.__setitem__(key[0], value)
            elif len(key) == 2:
                self._check_key_not_none(key[0])
                self._check_key_not_tuple(key[0])
                self._check_child(value)
                if key[1] == value._data:
                    self.__setitem__(key[0], value)
                else:
                    self.__getitem__(key).__setitem__((), value)
            elif len(key) % 2 == 0:
                self.__getitem__(key[:-2]).__setitem__(key[-2:], value)
            else:
                self.__getitem__(key[:-1]).__setitem__(key[-1:], value)
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
                c._key = None
            except KeyError:
                self._children[key] = []
            except StopIteration:
                pass
            value.detach()
            self._children[key].append(value)
            value._parent = self
            value._key = key


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

        if key is None:
            self._data = None
        elif isinstance(key, tuple):
            if len(key) == 0:
                self.detach()
            elif len(key) == 1:
                self._check_key_not_tuple(key[0])
                self.__delitem__(key[0])
            elif len(key) % 2 == 0:
                self.__getitem__(key).__delitem__(())
            else:
                self.__getitem__(key[:-1]).__delitem__(key[-1:])
        else:
            self._check_data(key)
            for child in self._children[key]:
                child._parent = None
                child._key = None
            del self._children[key]


    def detach(self):
        """Break connection between this node and its parent."""
        
        if self._parent is not None:
            # Remove self from parent's children
            del self._parent._children[self._key][
                next(i for i, sibling
                     in enumerate(self._parent._children[self._key])
                     if sibling is self)]
            # Remove empty exclusive set from parent
            if not self._parent._children[self._key]:
                del self._parent._children[self._key]
            # Remove parent information from self
            self._parent = None
            self._key = None


    def __invert__(self):
        return self._parent


    def __repr__(self):
        data_repr = repr(self._data) if self._data is not None else ''
        children_repr = repr(self._children) if self._children else ''
        return (self.__class__.__name__ + '('
                + data_repr + (', ' if data_repr and children_repr else '')
                + children_repr + ')')


    def __str__(self):
        return self._str()


    def _str(self, prefix='', next_sibling=False):
        CYAN = '\033[36m'
        YELLOW = '\033[33m'
        PURPLE = '\033[35m'
        RED = '\033[31m'
        GREEN = '\033[32m'
        BLUE = '\033[34m'
        NO_COLOR = '\033[0m'
        out = (prefix
               + ('\u251c' if next_sibling
                  else '\u2576' if prefix == ''
                  else '\u2570')
               + '\u2574'
               + (RED + '*' if self[None] is None
                  else (YELLOW + repr(self[None])))
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
                        + (RED + '*' if self._children[label][0][None] is None
                           else (YELLOW + repr(self._children[label][0][None])))
                        + NO_COLOR + '\n')
            else:
                out += (inner_prefix
                        + ('\u251c' if i < l - 1 else '\u2570')
                        + '\u2500\u256e '
                        + CYAN + repr(label) + NO_COLOR + '\n')
                for j, node in enumerate(self._children[label]):
                    out += node._str(inner_prefix + ('\u2502 ' if i < l - 1
                                                     else '  '),
                                     j < k - 1)
            if i < l - 1:
                out += (prefix
                        + ('\u2502' if next_sibling else ' ')
                        + GREEN + '\u2576' + NO_COLOR + '\u2502'
                        + GREEN + '\u254c\u254c\u254c\u254c\u254c' + NO_COLOR
                        + '\n')
        return out
        



# TODO Extend to more general tree types
# TODO Move to classes
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
        print(prefix + ('\u251c' if next_sibling else '\u2576' if prefix == '' else '\u2570') + '\u2574' + ('\033[36m*' if tree[None] is None else ('\033[33m' + str(tree[None]))) + '\033[0m')
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
    tree.data = 5
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
