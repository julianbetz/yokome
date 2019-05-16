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
