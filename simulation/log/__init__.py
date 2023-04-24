class Logger:
    """
    A class that logs messages to stdout.
    """

    def __init__(self, **kwargs: dict[str, int]):
        """
        The __init__ function initializes the class with a dictionary of column names and their widths.
        If no arguments are passed, it defaults to the following:
            {'Clock': 5, 'Event': 15, 'Description': 25}
        """
        self.COLUMNS = {'Clock': 5, 'Event': 15, 'Description': 25} if not kwargs else kwargs
        self.SEPARATOR = '+ ' + ' + '.join('-' * col_width for col_width in self.COLUMNS.values()) + ' +'
        self.ROW = '| ' + ' | '.join('{:<%d}' % col_width for col_width in self.COLUMNS.values()) + ' |'

    def begin(self) -> None:
        """
        The begin function prints the header for the table of events.

        :return: None
        """
        print(self.SEPARATOR)
        print(self.ROW.format(*self.COLUMNS.keys()))
        print(self.SEPARATOR)

    def end(self) -> None:
        """
        The end function prints the bottom of the table of events.

        :return: None
        """
        print(self.SEPARATOR)

    def log(self, *args: tuple[str, ...]) -> None:
        """
        The log function is used to print out the event log.
        It takes the values to print in a log.

        :param *args: tuple[str, ...]: Values to be logged
        :return: None
        """
        print(self.ROW.format(*args))
