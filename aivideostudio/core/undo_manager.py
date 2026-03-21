from collections import deque
from loguru import logger


class UndoManager:
    def __init__(self, max_size=100):
        self._undo_stack = deque(maxlen=max_size)
        self._redo_stack = deque(maxlen=max_size)

    def push(self, action_name, undo_fn, redo_fn):
        self._undo_stack.append((action_name, undo_fn, redo_fn))
        self._redo_stack.clear()
        logger.info("Action: " + action_name)

    def undo(self):
        if not self._undo_stack:
            logger.info("Nothing to undo")
            return False
        name, undo_fn, redo_fn = self._undo_stack.pop()
        undo_fn()
        self._redo_stack.append((name, undo_fn, redo_fn))
        logger.info("Undo: " + name)
        return True

    def redo(self):
        if not self._redo_stack:
            logger.info("Nothing to redo")
            return False
        name, undo_fn, redo_fn = self._redo_stack.pop()
        redo_fn()
        self._undo_stack.append((name, undo_fn, redo_fn))
        logger.info("Redo: " + name)
        return True

    def can_undo(self):
        return len(self._undo_stack) > 0

    def can_redo(self):
        return len(self._redo_stack) > 0

    def undo_name(self):
        if self._undo_stack:
            return self._undo_stack[-1][0]
        return ""

    def redo_name(self):
        if self._redo_stack:
            return self._redo_stack[-1][0]
        return ""
