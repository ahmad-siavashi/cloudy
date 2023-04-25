from __future__ import annotations


class Clock:
    """
    The simulator uses a clock to keep track of time. One tick equals one time unit. To make things easy, assume
    one tick equals one second.

    Attributes
    ==========
    - _tick (int, private): a private class variable to keep the current time
    """
    _tick: int = 0

    def reset(self) -> int:
        """
        The reset function resets the clock to 0.

        :return: The new current time
        """
        self._tick = 0
        return self.now()

    def increment(self, ticks: int = 1) -> int:
        """
        The increment function is used to increment the clock by a given number of ticks where each tick represents one simulation time unit.
        The default value for ticks is 1, so if no argument is passed in, the clock will be incremented by 1 tick.

        :param ticks: int: Increment the clock by a certain number of ticks
        :return: The new current time
        """
        self._tick += ticks
        return self.now()

    def now(self) -> int:
        """
        The now function returns the current time, which is stored in a private variable called _tick.

        :return: The value of the _tick attribute
        """
        return self._tick
