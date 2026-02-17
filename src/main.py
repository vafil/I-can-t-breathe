import random
import arcade

# базовая логика игры лежит в этом файле
from game_base import GameBase


class Game(GameBase):
    def update_animation(self, dt):
        self.anim_timer += dt
        fr = int(self.anim_timer / 0.2) % 2

        if self.p:
            # если игрок идёт, включаем второй кадр
            if self.p.change_x != 0 or self.p.change_y != 0:
                self.p.texture = self.player_tex[fr]
            else:
                self.p.texture = self.player_tex[0]

        for foe in self.foes:
            foe.texture = self.enemy_tex[fr]

    def make_particle(self, tex):
        return arcade.LifetimeParticle(
            filename_or_texture=tex,
            change_xy=(random.uniform(-1.5, 1.5), random.uniform(-1.5, 1.5)),
            lifetime=random.uniform(0.2, 0.5),
            scale=1.0,
            alpha=220,
        )

    def spawn_fx(self, pos, col):
        # простые частицы
        tex = arcade.make_soft_circle_texture(6, col, 96, 255)

        def particle_factory(_emitter):
            return self.make_particle(tex)

        em = arcade.Emitter(
            center_xy=pos,
            emit_controller=arcade.EmitterIntervalWithTime(0.02, 0.15),
            particle_factory=particle_factory,
        )
        self.emitters.append(em)


def main():
    Game()
    arcade.run()


if __name__ == "__main__":
    main()
