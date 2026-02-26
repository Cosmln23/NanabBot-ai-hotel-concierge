"""
Agent Runner - Backwards compatibility wrapper for brain.py
All logic has moved to brain.py - this is just for imports.
"""

from app.agent.brain import HotelBrain, process_with_brain


# Backwards compatibility alias
def agent_process_message(db, message):
    """Process message using the new brain."""
    return process_with_brain(db, message)


__all__ = ["agent_process_message", "process_with_brain", "HotelBrain"]
