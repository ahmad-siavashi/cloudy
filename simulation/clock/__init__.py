from __future__ import annotations

from typing import ClassVar


class Clock:
    """
    The simulator uses a clock to keep track of time. One tick equals one time unit. To make things easy, assume
    one tick equals one second.

    Attributes
    ==========
    - _tick (ClassVar[int], private): a private static class variable to keep the current time
    """
    _tick: ClassVar[int] = 0

    @staticmethod
    def reset() -> int:
        """
        The reset function resets the clock to 0.

        :return: The new current time
        """
        Clock._tick = 0
        return Clock.now()

    @staticmethod
    def increment(ticks=1) -> int:
        """
        The increment function is used to increment the clock by a given number of ticks where each tick represents one simulation time unit.
        The default value for ticks is 1, so if no argument is passed in, the clock will be incremented by 1 tick.

        :param ticks: Increment the clock by a certain number of ticks
        :return: The new current time
        """
        Clock._tick += ticks
        return Clock.now()

    @staticmethod
    def now() -> int:
        """
        The now function is a static method of the Clock class.
        It returns the current time, which is stored in a private variable called _tick.
        The now function can be used to get the current time without having to create an instance of Clock.

        :return: The value of the _tick attribute in the clock class
        """
        return Clock._tick
