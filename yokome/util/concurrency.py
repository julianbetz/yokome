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


import math
import asyncio
from multiprocessing import cpu_count
from psutil import virtual_memory


class SubprocessLock:
    """Context manager limiting the number of parallel processes."""

    _locks = 0
    """Current number of parallel subprocesses."""

    _MAX_LOCKS = cpu_count()
    """Maximum number of parallel subprocesses."""
    
    def __init__(self, sleep):
        self._sleep = sleep

    async def __aenter__(self):
        """Request a subprocess lock and wait for eventual permission."""
        while SubprocessLock._locks >= SubprocessLock._MAX_LOCKS:
            await asyncio.sleep(self._sleep)
        SubprocessLock._locks += 1

    async def __aexit__(self, exc_type, exc, tb):
        """Release the held subprocess lock."""
        # XXX May break if __aenter__ was exited prematurely
        SubprocessLock._locks -= 1


class MemoryLock:
    """Context manager for memory reservation.

    This does not lock the physical memory, but is only intended as a means of
    communication for multiple asynchronous tasks that jointly require more
    memory than the system is expected to be able to provide.

    Locking is solely based on the total size of the system memory and the
    **explicitly** requested memory size on entering the context manager.

    """

    _locks = 0
    """Current number of bytes reserved."""

    _MAX_LOCKS = max(math.floor(virtual_memory().total * 0.75),
                     virtual_memory().total - 1024 ** 3)
    """Maximum number of bytes available for reservation."""
    
    def __init__(self, sleep, request):
        if not isinstance(request, int) or request < 0:
            raise ValueError('Unable to request locks on %r bytes' % (request,))
        self._sleep = sleep
        self._request = request

    async def __aenter__(self):
        """Request the locking of bytes and wait for eventual permission."""
        while MemoryLock._locks + self._request > MemoryLock._MAX_LOCKS:
            await asyncio.sleep(self._sleep)
        MemoryLock._locks += self._request

    async def __aexit__(self, exc_type, exc, tb):
        """Release the held memory lock."""
        # XXX May break if __aenter__ was exited prematurely
        MemoryLock._locks -= self._request
