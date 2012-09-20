# A module to interactively extract information from users.
#
# Copyright (c) 2012 Dominic van Berkel.  See LICENSE for details.
#

# from questions import *

class Interro(object):
    """Core "interrogation" class.

    Keeps track of the questions in what is essentially a singly-linked list.
    Spits out questions, descriptive messages and errors, passes answers on to
    the InterroQ objects and asks for confirmation as needed.

    Usage:
    After instantiation InterroQ instances can be passed to add() which will
    add them to the list.  After start() is called, messages will be
    chronologically filled with messages from questions as they roll in.
    Submit answers through answer() as long as complete isn't True, then call
    results() to get a dictionary of results.  Terminates when an InterroQ is
    processed that doesn't actually have a question attached to it.

    """    
    def __init__(self, msg_callback=None, complete_callback=None):
        self.messages = []
        self.questions = {}
        self.answers = {}
        self.current = None
        self.complete = False
        self._pendinganswer = None
        self._pendingconfirmation = False
        self._msg = msg_callback or self.messages.append
        self._complete_callback = complete_callback

    def results(self):
        """Get a dictionary of {name: value} with the results so far"""
        return self.answers

    def add(self, question):
        """Add an InterroQ instance to the list."""
        self.questions[question.name] = question

    def start(self, start='start'):
        """Start pulling questions."""
        self._nextquestion(goto=start)

    def convo_complete(self):
        """Mark as complete and run complete_callback"""
        self.complete = True
        if self._complete_callback:
            self._complete_callback(self.results())

    def answer(self, value):
        """Process an answer.

        If we're waiting for confirmation, handle that and move to the next
        question if the answer is yes.  Otherwise, throw the answer at the
        current InterroQ to see if it validates, then store it and maybe ask
        for confirmation.

        """
        cur = self.current
        if self._pendingconfirmation:
            value = value.strip().lower()
            if value in ['yes', 'y']:
                self._nextquestion()
            else:
                self._msg(cur.question)
            self._pendingconfirmation = False
        else:
            # Throw the answer at the current question
            result, error = cur.process(value)
            if error is not None:
                self._msg('Error: {0}'.format(error))
                self._msg(cur.question)
            elif cur.confirm:
                # Ask for confirmation
                self.answers[cur.name] = result
                self._pendingconfirmation = True
                confirmq = 'You entered {value}.  Are you certain? [yes/no]'
                self._msg(confirmq.format(value=value))
            else:
                # No confirmation needed, so just store it
                self.answers[cur.name] = result
                self._nextquestion()

    def _nextquestion(self, goto=None):
        """Move to the next question, if any.

        Sets self.complete to true if the new InterroQ doesn't actually have a
        question, but does add its message - if any - to the message queue.

        """
        if self.current:
            # answer defaults to None when the current question didn't have an
            # answer - for instance, when it wasn't actually a question.
            answer = self.answers.get(self.current.name)
            nextq = self.current.nextq(answer)
        else:
            nextq = None
        if goto is None and nextq is None:
            self.convo_complete()
        else:
            goto = goto or nextq
            self.current = self.questions[goto]
            if self.current.question:
                self._msg(self.current.question)
            if self.current.message:
                self._msg(self.current.message)
            if not self.current.question:
                self._nextquestion()
