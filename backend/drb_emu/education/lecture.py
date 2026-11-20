from pathlib import Path

import pygame

from drb_emu.education.frame_labels import FrameLabel
from drb_emu.education.subtitles import SubtitleViewer

EDUCATION_DIR = Path(__file__).parent


class LectureAnimation:
    def __init__(self):
        self.image_path = EDUCATION_DIR / "databricks.png"
        self.narration_path = EDUCATION_DIR / "lektor.mp3"
        self.subtitles_path = EDUCATION_DIR / "lektor.srt"
        self.subtitle_area_height = 140
        self.background_color = (16, 20, 28)
        self.frames_per_second = 60
        self.title = "drb-emu - Lakehouse"

    def run(self):
        pygame.init()
        try:
            self._play()
        finally:
            pygame.quit()

    def _play(self):
        picture = pygame.image.load(str(self.image_path))
        screen = pygame.display.set_mode((picture.get_width(), picture.get_height() + self.subtitle_area_height))
        pygame.display.set_caption(self.title)
        picture = picture.convert_alpha()
        subtitle_center_y = picture.get_height() + self.subtitle_area_height // 2
        subtitle_viewer = SubtitleViewer(self.subtitles_path, subtitle_center_y)
        frame_labels = self._create_frame_labels()

        pygame.mixer.music.load(str(self.narration_path))
        pygame.mixer.music.play()

        clock = pygame.time.Clock()
        playback_position_ms = -1
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    running = False
            screen.fill(self.background_color)
            screen.blit(picture, (0, 0))
            playback_position_ms = max(playback_position_ms, pygame.mixer.music.get_pos())
            for frame_label in frame_labels:
                frame_label.draw(screen, playback_position_ms)
            subtitle_viewer.draw(screen, playback_position_ms)
            pygame.display.flip()
            clock.tick(self.frames_per_second)
            if not pygame.mixer.music.get_busy():
                running = False
        pygame.mixer.music.stop()

    def _create_frame_labels(self):
        roof_frame = (687, 100, 280, 57)
        shelf_frames = [(558, 272, 165, 35), (558, 379, 165, 35), (558, 482, 165, 35)]
        book_pile_frames = [(780, 437, 144, 24), (784, 476, 141, 24), (780, 516, 143, 24)]
        above_computer_and_librarian = (985, 312, 200, 34)
        above_people_upper_line = (20, 250, 360, 44)
        above_people_lower_line = (20, 296, 360, 44)
        return [
            FrameLabel(17_000, "LAKEHOUSE", [roof_frame]),
            FrameLabel(22_000, "CLOUD STORAGE", shelf_frames),
            FrameLabel(55_000, "DATA LAKE FORMAT", book_pile_frames),
            FrameLabel(90_000, "UNITY CATALOG", [above_computer_and_librarian]),
            FrameLabel(128_000, "CLUSTERS", [above_people_upper_line]),
            FrameLabel(128_000, "SQL WAREHOUSES", [above_people_lower_line]),
        ]


if __name__ == "__main__":
    LectureAnimation().run()
