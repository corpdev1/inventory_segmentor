import re
from typing import List




class MaskingInstruction:
    def __init__(self, regex_pattern: str, mask_with: str):
        self.regex_pattern = regex_pattern
        self.mask_with = mask_with
        self.regex = re.compile(regex_pattern)


class RegexMasker:
    def __init__(self, masking_instructions: List[MaskingInstruction]):
        self.masking_instructions = masking_instructions


    def mask(self, content: str):
        for mi in self.masking_instructions:
            # content = re.sub(mi.regex, mi.mask_with_wrapped, content)
            content = mi.regex.sub( mi.mask_with , content)
        return content



class LogMasker:
    def __init__(self, masking_instructions: List[MaskingInstruction]):
        self.masker = RegexMasker(masking_instructions)

    def mask(self, content: str):
        if self.masker is not None:
            return self.masker.mask(content)
        else:
            return content