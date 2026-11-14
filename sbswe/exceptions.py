class InterruptAgentFlow(Exception):
    def __init__(self, *messages):
        self.messages = messages
        super().__init__()

class Submitted(InterruptAgentFlow):
    pass

class LimitsExceeded(InterruptAgentFlow):
    pass

class TimeExceeded(LimitsExceeded):
    pass
