import pygame


class FrameLabel:
    def __init__(self, appears_at_ms, text, frames, font="Arial"):
        self.appears_at_ms = appears_at_ms
        self.text = text
        self.frames = [pygame.Rect(frame) for frame in frames]
        self.font_name = font
        self.color = (20, 24, 40)
        self.padding = 4
        self.largest_font_size = 40
        self.fade_in_ms = 600
        self.rendered_texts = [self._render_fitting(frame) for frame in self.frames]

    def _render_fitting(self, frame):
        available_width = frame.width - 2 * self.padding
        available_height = frame.height - 2 * self.padding
        for font_size in range(self.largest_font_size, 5, -1):
            font = pygame.font.SysFont(self.font_name, font_size, bold=True)
            text_width, text_height = font.size(self.text)
            if text_width <= available_width and text_height <= available_height:
                return font.render(self.text, True, self.color)
        return pygame.font.SysFont(self.font_name, 6, bold=True).render(self.text, True, self.color)

    def draw(self, surface, position_ms):
        elapsed_ms = position_ms - self.appears_at_ms
        if elapsed_ms < 0:
            return
        opacity = min(255, int(255 * elapsed_ms / self.fade_in_ms))
        for frame, rendered_text in zip(self.frames, self.rendered_texts):
            rendered_text.set_alpha(opacity)
            surface.blit(rendered_text, rendered_text.get_rect(center=frame.center))
