from __future__ import annotations

import random
import arcade

# Берём базовую игру из второго файла.
# Если файл game_base.py не создан — Python сразу скажет, что не может импортировать.
from game_base import GameBase


class Game(GameBase):
    def update_animation(self, dt: float) -> None:
        self.anim_timer += dt
        fr = int(self.anim_timer / 0.2) % 2

        if self.p:
            if abs(self.p.change_x) > 0 or abs(self.p.change_y) > 0:
                self.p.texture = self.player_tex[fr]
            else:
                self.p.texture = self.player_tex[0]

        for foe in self.foes:
            foe.texture = self.enemy_tex[fr]

    def spawn_fx(self, pos: tuple[float, float], col: arcade.Color) -> None:
        # простые частицы
        tex = arcade.make_soft_circle_texture(6, col, 96, 255)
        em = arcade.Emitter(
            center_xy=pos,
            emit_controller=arcade.EmitterIntervalWithTime(0.02, 0.15),
            particle_factory=lambda e: arcade.LifetimeParticle(
                filename_or_texture=tex,
                change_xy=(random.uniform(-1.5, 1.5), random.uniform(-1.5, 1.5)),
                lifetime=random.uniform(0.2, 0.5),
                scale=1.0,
                alpha=220,
            ),
        )
        self.emitters.append(em)


def main() -> None:
    Game()
    arcade.run()


if __name__ == "__main__":
    main()
