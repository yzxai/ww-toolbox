from abc import abstractmethod

from toolbox.core.interaction import Interaction


class BaseTask:
    def __init__(self):
        self.interaction = Interaction()

    @abstractmethod
    def run(self, **kwargs):
        pass