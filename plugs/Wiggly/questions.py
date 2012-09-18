# InterroQ and its various subclasses.
#
# Copyright (c) 2012 Dominic van Berkel.  See LICENSE for details.
#

class InterroQ:
    """Base class for Interro questions.  

    InterroQ has some infrastructure for validation checks, type checks that
    more specific question types can use and answer-dependant branching.

    Usage: 
    Create an instance with whatever parameters you like.  When you've got an
    answer, run it through .validate() to make sure it's of the right format.
    When that's done it can be stored with .store(), which will automatically
    run the value through .parse() in order to convert it to an appropriate
    type, format or otherwise.  Mostly it's expected that values thrown at 
    InterroQ are all strings.

    Interesting functions to override: 
    - parse: Takes a value and returns a format-appropriate representiation.
      See YesNoQ for an example.
    - add_typechecks: This is where subclasses can specify their type checks.
    - preprocess: General processing that should be done first, such as
      str.strip() and .lower()

    """
    def __init__(self, name, question=None, message=None, default_next=None, 
                 onanswer=None, validation=None, confirm=False):
        """Create an InterroQ instance.

        Parameters:
        - name: name of the question.  Can be used to identify the information.
        - question: The question to be asked.  
        - message: A message that will be shown when a question comes up for the
          first time.
        - default: The name of the question that should come after by default.
        - onanswer: a dictionary of {value: InterroQ}.  If the stored and
          parsed answer matches a value, this indicates what question to pull
          up next.
        - validation: A list of (method: error) tuples. 
        - confirm: Indicates whether the question requires confirmation.

        """
        self.name = name
        self.question = question
        self.message = message
        self.default_next = default_next
        self.onanswer = onanswer or {}
        self.validation = validation or []
        self.confirm = confirm
        self.error = None
        self.value = None
        self.add_typechecks()

    def add_typechecks(self, *args):
        """Add typechecks.

        The advice for subclasses is to construct a list of (method, error)
        and throw that at super() together with *args.

        """
        self.type_validation = args

    def preprocess(self, value):
        """Cleanup and essential formatting of input.

        Should be called by validate() and parse() before doing anything with
        the input.

        """
        return value

    def validate(self, value):
        """Runs the value through all known tests.

        Starts with type validation, then moves on to user-configured 
        requirements.

        """
        value = self.preprocess(value)
        for test, error in self.type_validation:
            if not test(value):
                self.error = error
                return False
        for test, error in self.validation:
            if not test(value):
                self.error = error
                return False
        self.error = None
        return True

    def parse(self, value):
        """Convert the value to someting appropriate for the question type.

        For example, YesNoQ turns it into a boolean, while a NumberQ might
        change it into an integer or float.  It's okay if this raises an
        exception on failure, as the type-specific validation checks should
        already make sure that it can be converted in the first place.

        """
        return self.preprocess(value)

    def store(self, value):
        """Parse and store the input."""
        self.value = self.parse(value)

    def nextq(self):
        """Find out what the next question is based on the current value."""
        if self.onanswer and self.value in self.onanswer:
            return self.onanswer[self.value]
        else:
            return self.default_next
            

class TextQ(InterroQ):
    """Text question class.

    Does very little, other than - if desired - making sure the input isn't
    empty and trimming the sides.

    """

    empty_allowed = False

    def __init__(self, name, empty_allowed=False, **kwargs):
        self.empty_allowed = empty_allowed
        super().__init__(name, **kwargs)

    def add_typechecks(self, *args):
        empty = (self.test_empty, 'This may not be empty.')
        super().add_typechecks(empty, *args)

    def preprocess(self, value):
        return value.strip()

    def test_empty(self, value):
        if self.empty_allowed:
            return True
        else:
            if value not in [None, '']:
                return True
            else:
                return False


class YesNoQ(InterroQ):
    """Yes/No-question class."""

    def add_typechecks(self, *args):
        yesno = (lambda x: x in ['y', 'yes', 'n', 'no'], 'Please enter yes or no.')
        super().add_typechecks(yesno, *args)

    def preprocess(self, value):
        return value.strip().lower()

    def parse(self, value):
        value = self.preprocess(value)
        if value in ['y', 'yes']:
            return True
        else:
            return False


class MessageQ(InterroQ):
    """Subclass that can only have a message.

    Mostly exists so you don't have to use InterroQ for this sort of thing.

    """
    def __init__(self, name, message='', default_next=None, **kwargs):
        super().__init__(name, message=message, default_next=default_next)


class NumberQ(InterroQ):
    req_positive = False
    def __init__(self, name, req_positive=False, **kwargs):
        self.req_positive = req_positive
        super().__init__(name, **kwargs)

    def add_typechecks(self, *args):
        number = (self.check_number, 'Please enter a whole number')
        positive = (self.check_positive, 'Please enter a positive number')
        super().add_typechecks(number, positive, *args)

    def preprocess(self, value):
        return value.strip()

    def check_number(self, value):
        try:
            num = int(value)
        except ValueError:
            return False
        return True

    def check_positive(self, value):
        if self.req_positive:
            try:
                value = int(value)
            except:
                return False
            if value < 0:
                return False
        return True

    def parse(self, value):
        value = self.preprocess(value)
        return int(value)
