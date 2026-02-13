"""
Simple text scratchpad for agent note-taking
"""


class Scratchpad:
    def __init__(self):
        self.content = ""

    def write(self, text: str) -> str:
        """Append text to scratchpad"""
        self.content += text + "\n"
        return f"Written to scratchpad ({len(self.content)} chars total)"

    def read(self) -> str:
        """Read full scratchpad content"""
        if not self.content:
            return "Scratchpad is empty."
        return self.content

    def erase(self) -> str:
        """Clear the scratchpad"""
        self.content = ""
        return "Scratchpad cleared."
