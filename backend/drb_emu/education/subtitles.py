import re
from dataclasses import dataclass
from pathlib import Path

import pygame

TIMESTAMP_LINE = re.compile(
    r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)"
)


@dataclass(frozen=True)
class Subtitle:
    start_ms: int
    end_ms: int
    text: str


def _to_ms(hours, minutes, seconds, millis):
    return ((int(hours) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + int(millis)


def parse_srt(path):
    subtitles = []
    blocks = re.split(r"\r?\n\s*\r?\n", Path(path).read_text(encoding="utf-8-sig"))
    for block in blocks:
        lines = [line.strip() for line in block.strip().splitlines()]
        for index, line in enumerate(lines):
            match = TIMESTAMP_LINE.search(line)
            if match:
                text = " ".join(part for part in lines[index + 1:] if part)
                subtitles.append(Subtitle(_to_ms(*match.groups()[:4]), _to_ms(*match.groups()[4:]), text))
                break
    return subtitles


class SubtitleViewer:
    def __init__(self, subtitles_path, y, font="Arial"):
        self.subtitles = parse_srt(subtitles_path)
        self.y = y
        self.font = pygame.font.SysFont(font, 28)
        self.color = (255, 255, 255)
        self.shadow_color = (0, 0, 0)
        self.shadow_offset = 2
        self.line_spacing = 4
        self.side_margin = 40

    def subtitle_at(self, position_ms):
        for subtitle in self.subtitles:
            if subtitle.start_ms <= position_ms < subtitle.end_ms:
                return subtitle
        return None

    def _wrap(self, text, max_width):
        lines = []
        current_line = ""
        for word in text.split():
            candidate = f"{current_line} {word}".strip()
            if current_line and self.font.size(candidate)[0] > max_width:
                lines.append(current_line)
                current_line = word
            else:
                current_line = candidate
        if current_line:
            lines.append(current_line)
        return lines

    def draw(self, surface, position_ms):
        subtitle = self.subtitle_at(position_ms)
        if subtitle is None:
            return
        center_x = surface.get_width() // 2
        lines = self._wrap(subtitle.text, surface.get_width() - 2 * self.side_margin)
        line_height = self.font.get_linesize() + self.line_spacing
        top = self.y - (len(lines) * line_height) // 2
        for line_index, line in enumerate(lines):
            line_center_y = top + line_index * line_height + line_height // 2
            shadow = self.font.render(line, True, self.shadow_color)
            surface.blit(shadow, shadow.get_rect(center=(center_x + self.shadow_offset, line_center_y + self.shadow_offset)))
            rendered = self.font.render(line, True, self.color)
            surface.blit(rendered, rendered.get_rect(center=(center_x, line_center_y)))
