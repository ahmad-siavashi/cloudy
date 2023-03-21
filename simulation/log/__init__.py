class Logger:
    """
    A class that logs messages to stdout.
    """

    @staticmethod
    def begin() -> None:
        """
        The begin function prints the header for the table of events.

        :return: None
        """
        print('+ {:<5} + {:<4} + {:<15} + {:<25} +'.format('-' * 5, '-' * 4, '-' * 15, '-' * 25))
        print('| {:<5} | {:<4} | {:<15} | {:<25} |'.format('Clock', 'Sign', 'Event Type', 'Description'))
        print('+ {:<5} + {:<4} + {:<15} + {:<25} +'.format('-' * 5, '-' * 4, '-' * 15, '-' * 25))

    @staticmethod
    def end() -> None:
        """
        The end function prints the bottom of the table of events.

        :return: None
        """
        print('+ {:<5} + {:<4} + {:<15} + {:<25} +'.format('-' * 5, '-' * 4, '-' * 15, '-' * 25))

    @staticmethod
    def log(clock: int, sign: str, type: str, description: str) -> None:
        """
        The log function is used to print out the event log.
        It takes in a clock, sign, event type and description as parameters.
        The clock parameter is an integer that represents the current time of the simulation.
        The sign parameter is a character that visualizes the type of event (e.g. error, info, etc)
        The type parameter is a string that describes the type of event
        The description parameter provides more information about the event

        :param clock: int: Keep track of the time
        :param sign: str: Visual indicator for the event
        :param type: str: Specify the type of event
        :param description: str: Describe the event that is being logged
        :return: None
        """
        print('| {:<5} | {:<4} | {:<15} | {:<25} |'.format(clock, sign, type, description))
