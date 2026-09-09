class AIAgentError(Exception):
    """
    Root of every error this project raises deliberately.

    Catching AIAgentError catches anything the project itself signalled, and
    lets genuinely unexpected errors (bugs) escape uncaught.
    """
